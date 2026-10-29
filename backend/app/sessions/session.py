from copy import deepcopy
from pydantic import JsonValue

import asyncio
from datetime import datetime, timedelta, timezone

import random

from math import ceil, sqrt

from backend.app.naming.generator import generate_unique_name, validate_name
from backend.app.sessions.player import Player
from backend.app.games.quiplash.prompts import QUIPLASH_PROMPTS

class Session:
    def __init__(self, session_id: str, host_name: str = "Host", settings: dict[str, JsonValue] | None = None, password: str | None = None):
        self.session_id = session_id
        self.host_name = host_name
        self.settings = deepcopy(settings) if settings is not None else {}
        self.password = password

        self.players: dict[str, "Player"] = {}

        options = self.settings.get("options", {})
        self.total_rounds: int = self.settings.get("rounds", 3)
        self.auto_generate_names: bool = isinstance(options, dict) and options.get("autoGenerateNames") is True
        self.used_names: set[str] = set()
        self.use_profanity_filter: bool = isinstance(options, dict) and options.get("useProfanityFilter") is True
        self.allow_late_join: bool = isinstance(options, dict) and options.get("allowLateJoin") is True
        self.requires_password: bool = isinstance(options, dict) and options.get("requiresPassword") is True

        # Game configuration
        self.game_id: str | None = None
        self.minimum_players: int | None = None
        self.maximum_players: int | None = None
        self.game_started: bool = False
        # Gameplay state
        self.current_round: int = 0
        self.current_prompt: str | None = None
        self.answers: dict[str, str] = {}

        # Subgroup assignments for each submission round.
        # Round number -> list of groups -> player IDs.
        self.round_groups: dict[int, list[list[str]]] = {}

        # Answers grouped by round and prompt-group index.
        # Round -> group index -> player ID -> answer.
        self.group_answers: dict[int, dict[int, dict[str, str]]] = {}

        # Votes grouped by round and prompt group.
        # Round -> group index -> voter ID -> answer owner's player ID.
        self.group_votes: dict[int, dict[int, dict[str, str]]] = {}

        # Total points earned by each player.
        self.scores: dict[str, int] = {}

        # Round -> group index -> prompt.
        self.group_prompts: dict[int, dict[int, str]] = {}

        # Round timer state
        self.round_duration_seconds: int | None = None
        self.round_deadline: datetime | None = None
        self.round_timer_task: asyncio.Task | None = None

        self.phase: str = "lobby"


    def set_auto_generate(self, enabled: bool) -> None:
        self.auto_generate_names = enabled

    def set_profanity_filter(self, enabled: bool) -> None:
        self.use_profanity_filter = enabled

    def set_allow_late_join(self, enabled: bool) -> None:
        self.allow_late_join = enabled

    def add_used_name(self, name: str) -> None:
        self.used_names.add(name)

    def remove_used_name(self, name: str) -> None:
        self.used_names.discard(name)
    
    def assign_name(self, requested_name: str | None = None) -> str:
        if requested_name is not None:
            if requested_name.casefold() in {name.casefold() for name in self.used_names}:
                raise ValueError("That name is already taken.")
            if self.use_profanity_filter == True:
                valid = validate_name(requested_name)
                if not valid:
                    raise ValueError("Name contains inappropriate content.")
            self.add_used_name(requested_name)
            return requested_name

        if self.auto_generate_names:
            name = generate_unique_name(self.used_names)
            self.add_used_name(name)
            return name

        raise ValueError("Name must be provided or auto-generation must be enabled.")

    def add_player(self, player_id: str, requested_name: str | None = None) -> Player:
        name = self.assign_name(requested_name)
        player = Player(player_id, name)
        self.players[player_id] = player
        return player

    def remove_player(self, player_id: str) -> None:
        if player_id in self.players:
            player = self.players.pop(player_id)
            self.remove_used_name(player.name)

    def get_player(self, player_id: str) -> Player | None:
        return self.players.get(player_id)

    
    def get_player_group_index(self, round_number: int, player_id: str) -> int:
        """Return the index of the group containing a player in a round."""
        groups = self.round_groups.get(round_number)

        if groups is None:
            raise ValueError("Groups have not been generated for this round.")

        for group_index, group in enumerate(groups):
            if player_id in group:
                return group_index

        raise ValueError("Player is not assigned to a group in this round.")

        
    def submit_answer(self, player_id: str, answer: str) -> None:
        if not self.game_started:
            raise ValueError("The game has not started.")

        if self.game_id != "quiplash":
            raise ValueError("This game does not accept quip answers.")

        if self.get_player(player_id) is None:
            raise ValueError("Player not found.")

        if not answer.strip():
            raise ValueError("Answer cannot be empty.")

        if len(answer) > 200:
            raise ValueError("Answer cannot exceed 200 characters.")

        if self.use_profanity_filter:
            valid = validate_name(answer)
            if not valid:
                raise ValueError("Answer contains inappropriate content.")

        round_number = self.current_round

        if round_number not in self.round_groups:
            raise ValueError("Groups have not been generated for this round.")

        group_index = self.get_player_group_index(round_number, player_id)

        round_answers = self.group_answers.setdefault(round_number, {})
        group_answers = round_answers.setdefault(group_index, {})

        group_answers[player_id] = answer

    def submit_vote(
        self,
        voter_id: str,
        group_index: int,
        answer_owner_id: str,
    ) -> None:
        if self.phase != "voting":
            raise ValueError("Voting is not currently open.")

        round_number = self.current_round

        if voter_id not in self.players:
            raise ValueError("Voter is not in this session.")

        if answer_owner_id not in self.players:
            raise ValueError("Answer owner is not in this session.")

        groups = self.round_groups.get(round_number, [])

        if group_index < 0 or group_index >= len(groups):
            raise ValueError("Invalid group.")

        # Find the voter's group and the answer owner's group.
        voter_group_index = self.get_player_group_index(
            round_number,
            voter_id,
        )
        owner_group_index = self.get_player_group_index(
            round_number,
            answer_owner_id,
        )

        if voter_group_index is None or owner_group_index is None:
            raise ValueError("Player is not assigned to a group.")

        # Players cannot vote on their own group's answers.
        if group_index == voter_group_index:
            raise ValueError("You cannot vote in your own group.")

        # The answer must belong to the group being voted on.
        if owner_group_index != group_index:
            raise ValueError("That answer is not in the selected group.")

        if voter_id == answer_owner_id:
            raise ValueError("You cannot vote for your own answer.")

        group_answers = self.group_answers.get(
            round_number, {}
        ).get(group_index, {})

        if answer_owner_id not in group_answers:
            raise ValueError("That player has no answer to vote for.")

        # Store the vote under the TARGET group, not the voter's group.
        round_votes = self.group_votes.setdefault(round_number, {})
        group_votes = round_votes.setdefault(group_index, {})

        if voter_id in group_votes:
            raise ValueError("You have already voted in this group.")

        group_votes[voter_id] = answer_owner_id
        self.scores[answer_owner_id] = (
            self.scores.get(answer_owner_id, 0) + 1
        )

    def all_players_submitted(self, round_number: int) -> bool:
        """Return whether every player assigned to this round submitted an answer."""
        groups = self.round_groups.get(round_number)

        if groups is None:
            raise ValueError("Groups have not been generated for this round.")

        round_answers = self.group_answers.get(round_number, {})

        for group_index, group in enumerate(groups):
            submitted = round_answers.get(group_index, {})

            for player_id in group:
                if player_id not in submitted:
                    return False

        return True


    def configure_game(self, game_id: str, minimum_players: int, maximum_players: int) -> None:
        if self.game_started:
            raise ValueError("Cannot configure a game that has started.")

        if minimum_players < 1:
            raise ValueError("Minimum players must be at least 1.")

        if maximum_players < minimum_players:
            raise ValueError(
                "Maximum players must be greater than or equal to "
                "minimum players."
            )

        if len(self.players) > maximum_players:
            raise ValueError(
                "The current player count exceeds the maximum player limit."
            )

        self.game_id = game_id
        self.minimum_players = minimum_players
        self.maximum_players = maximum_players

    def can_start_game(self) -> bool:
        if self.game_started:
            return False

        if self.game_id is None:
            return False

        if self.minimum_players is None:
            return False

        if self.maximum_players is None:
            return False

        player_count = len(self.players)

        return (
            player_count >= self.minimum_players
            and player_count <= self.maximum_players
        )

    # def start_game(self) -> None:
    #     if self.game_started:
    #         raise ValueError("Game has already started.")

    #     if not self.can_start_game():
    #         raise ValueError(
    #             "Game cannot start because the start conditions "
    #             "have not been met."
    #         )

    #     self.current_prompt = QUIPLASH_PROMPTS[0]
    #     self.current_round = 1
    #     self.game_started = True

    
    def start_game(self) -> None:
        if self.game_started:
            raise ValueError("Game has already started.")

        if not self.can_start_game():
            raise ValueError(
                "Game cannot start because the start conditions "
                "have not been met."
            )

        if self.game_id == "quiplash":
            self.generate_round_groups()
            self.assign_group_prompts()

            self.current_round = 1
            self.current_prompt = next(
                iter(self.group_prompts[self.current_round].values())
            )
        else:
            self.current_prompt = QUIPLASH_PROMPTS[0]
            self.current_round = 1

        self.game_started = True
        self.phase = "answering"


    def regenerate_name(self, player_id: str) -> str: 
        player = self.get_player(player_id)
        if player is None:
            raise ValueError(f"Player with ID {player_id} does not exist.")

        self.remove_used_name(player.name)
        new_name = self.assign_name()
        player.name = new_name
        return new_name

    def set_player_ready(self, player_id: str, ready: bool) -> Player:
        player = self.get_player(player_id)
        if player is None:
            raise ValueError("Player not found")
        player.ready = ready
        return player

    def kick_player(self, player_id: str) -> None:
        player = self.get_player(player_id)
        if player is None:
            raise ValueError(f"Player with ID {player_id} does not exist.")
        self.remove_player(player.player_id)

    def hide_player(self, player_id: str, hidden: bool = True) -> Player:
        player = self.get_player(player_id)
        if player is None:
            raise ValueError(f"Player with ID {player_id} does not exist.")
        player.hidden = hidden
        return player

    # def advance_round(self) -> None:
    #     if not self.game_started:
    #         raise ValueError("The game has not started.")

    #     if self.game_id != "quiplash":
    #         raise ValueError("This game does not support rounds.")

    #     next_round = self.current_round + 1

    #     if next_round > self.total_rounds:
    #         raise ValueError("There are no more rounds.")

    #     self.current_round = next_round
    #     self.current_prompt = QUIPLASH_PROMPTS[next_round - 1]
    #     self.answers.clear()

    
    def advance_round(self) -> None:
        if not self.game_started:
            raise ValueError("The game has not started.")

        if self.game_id != "quiplash":
            raise ValueError("This game does not support rounds.")

        next_round = self.current_round + 1

        if next_round > self.total_rounds:
            self.phase = "finished"
            return

        if next_round not in self.group_prompts:
            raise ValueError("Prompts have not been assigned for the next round.")

        self.current_round = next_round
        self.phase = "answering"

        # Keep a default prompt temporarily for compatibility with existing routes.
        self.current_prompt = next(iter(self.group_prompts[next_round].values()))

        # Do not clear group_answers: previous rounds' answers must remain available.
        self.answers.clear()


    def mod_player(self, player_id: str, is_mod: bool) -> Player:
        player = self.get_player(player_id)
        if player is None:
            raise ValueError(f"Player with ID {player_id} does not exist.")
        player.is_mod = is_mod
        return player

    
    
    
    def generate_round_groups(self) -> dict[int, list[list[str]]]:
        """Generate balanced groups while minimizing repeated pairings."""
        player_ids = list(self.players.keys())
        player_count = len(player_ids)

        if player_count < 2:
            raise ValueError("At least two players are needed to form groups.")

        if self.total_rounds < 1:
            raise ValueError("At least one round is required.")

        if self.total_rounds > 5:
            raise ValueError("A maximum of five rounds is supported.")

        # Calculate the maximum feasible number of groups.
        max_groups_by_players = player_count // 2
        max_groups_by_prompts = len(QUIPLASH_PROMPTS) // self.total_rounds

        if max_groups_by_prompts < 1:
            raise ValueError("Not enough unique prompts for the selected rounds.")

        # Favor groups of two while respecting prompt availability.
        group_count = min(
            max_groups_by_players,
            max_groups_by_prompts,
        )

        groups_by_round: dict[int, list[list[str]]] = {}
        previous_pairings: dict[tuple[str, str], int] = {}

        for round_number in range(1, self.total_rounds + 1):
            best_groups = None
            best_score = float("inf")

            # Search randomized arrangements to minimize repeated pairings.
            for _ in range(500):
                shuffled = player_ids.copy()
                random.shuffle(shuffled)

                groups = [[] for _ in range(group_count)]

                # Distribute players as evenly as possible.
                for index, player_id in enumerate(shuffled):
                    groups[index % group_count].append(player_id)

                # Penalize pairings based on how often they have occurred.
                score = sum(
                    1 + previous_pairings.get(
                        tuple(sorted((player_a, player_b))), 0
                    )
                    for group in groups
                    for i, player_a in enumerate(group)
                    for player_b in group[i + 1:]
                )

                if score < best_score:
                    best_score = score
                    best_groups = groups

                # Stop early if this arrangement introduces no repeated pairs.
                if all(
                    previous_pairings.get(
                        tuple(sorted((player_a, player_b))), 0
                    ) == 0
                    for group in groups
                    for i, player_a in enumerate(group)
                    for player_b in group[i + 1:]
                ):
                    break

            assert best_groups is not None
            groups_by_round[round_number] = best_groups

            # Record pairings for use when generating subsequent rounds.
            for group in best_groups:
                for i, player_a in enumerate(group):
                    for player_b in group[i + 1:]:
                        pairing = tuple(sorted((player_a, player_b)))
                        previous_pairings[pairing] = (
                            previous_pairings.get(pairing, 0) + 1
                        )

        self.round_groups = groups_by_round
        return groups_by_round



    
    def assign_group_prompts(self) -> dict[int, dict[int, str]]:
        """Assign a distinct prompt to each group, avoiding reuse when possible."""
        prompts = QUIPLASH_PROMPTS.copy()
        random.shuffle(prompts)

        required_prompts = sum(
            len(groups) for groups in self.round_groups.values()
        )

        if required_prompts > len(prompts):
            raise ValueError(
                "Not enough unique prompts for all groups across all rounds."
            )

        group_prompts: dict[int, dict[int, str]] = {}
        prompt_index = 0

        for round_number, groups in self.round_groups.items():
            group_prompts[round_number] = {}

            for group_index, _group in enumerate(groups):
                group_prompts[round_number][group_index] = prompts[prompt_index]
                prompt_index += 1

        self.group_prompts = group_prompts
        return group_prompts

