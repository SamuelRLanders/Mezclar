from copy import deepcopy
from pydantic import JsonValue

from backend.app.naming.generator import generate_unique_name, validate_name
from backend.app.sessions.player import Player
from backend.app.games.quiplash.prompts import QUIPLASH_PROMPTS

class Session:
    def __init__(self, session_id: str, host_name: str = "Host", settings: dict[str, JsonValue] | None = None):
        self.session_id = session_id
        self.host_name = host_name
        self.settings = deepcopy(settings) if settings is not None else {}

        self.players: dict[str, "Player"] = {}

        options = self.settings.get("options", {})
        self.auto_generate_names: bool = isinstance(options, dict) and options.get("autoGenerateNames") is True
        self.used_names: set[str] = set()
        self.use_profanity_filter: bool = isinstance(options, dict) and options.get("useProfanityFilter") is True
        self.allow_late_join: bool = isinstance(options, dict) and options.get("allowLateJoin") is True

        # Game configuration
        self.game_id: str | None = None
        self.minimum_players: int | None = None
        self.maximum_players: int | None = None
        self.game_started: bool = False
        self.game_completed: bool = False
        # Gameplay state
        self.current_round: int = 0
        self.current_prompt: str | None = None
        self.answers: dict[str, str] = {}

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

    def submit_answer(self, player_id: str, answer: str) -> None:
        if self.game_completed:
            raise ValueError("The game has finished.")

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

        self.answers[player_id] = answer

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

    def start_game(self) -> None:
        if self.game_started:
            raise ValueError("Game has already started.")

        if not self.can_start_game():
            raise ValueError(
                "Game cannot start because the start conditions "
                "have not been met."
            )

        self.current_prompt = QUIPLASH_PROMPTS[0]
        self.current_round = 1
        self.game_started = True

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

    def advance_round(self) -> None:
        if self.game_completed:
            raise ValueError("The game has finished.")

        if not self.game_started:
            raise ValueError("The game has not started.")

        if self.game_id != "quiplash":
            raise ValueError("This game does not support rounds.")

        next_round = self.current_round + 1

        if next_round > len(QUIPLASH_PROMPTS):
            self.game_completed = True
            return

        self.current_round = next_round
        self.current_prompt = QUIPLASH_PROMPTS[next_round - 1]
        self.answers.clear()

    def mod_player(self, player_id: str, is_mod: bool) -> Player:
        player = self.get_player(player_id)
        if player is None:
            raise ValueError(f"Player with ID {player_id} does not exist.")
        player.is_mod = is_mod
        return player
