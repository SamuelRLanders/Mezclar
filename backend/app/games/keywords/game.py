"""

Keywords Game Logic

Players are split into small groups. Everyone in a group shares a secret
keyword except one faker, who has to blend in. Each group moves through its
own phases independently of the other groups:

gathering -> roles -> speaking -> voting -> reveal

"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from math import ceil

from backend.app.games.keywords.words import KEYWORDS

# Smallest game that can be played: two players who know the word plus one faker.
MIN_PLAYERS = 3
# Largest group size; more players than this means more groups.
MAX_GROUP_SIZE = 6
# Longest name or keyword guess a player may type in the voting phase.
MAX_ANSWER_LENGTH = 50

# Each group is shown one of these colors so its members can find each other.
GROUP_COLORS = ["Red", "Blue", "Green", "Yellow", "Purple", "Orange", "Pink", "Teal"]

# The phases every group moves through, in order.
GATHERING = "gathering"
ROLES = "roles"
SPEAKING = "speaking"
VOTING = "voting"
REVEAL = "reveal"


def normalize(text: str) -> str:
    # Collapse whitespace and ignore case so "  ice  CREAM " matches "Ice Cream".
    return " ".join(text.split()).casefold()


@dataclass
class KeywordsGroup:
    """
    The full state of one group. Fields are grouped by the phase that uses them;
    a field for a later phase stays empty until the group reaches that phase.
    """

    # Position of this group in KeywordsGame.groups.
    index: int
    # Color name used to style the group's screens, e.g. "Red".
    color: str
    # Name shown to players; "Red", or "Red 2" once all the colors are in use.
    label: str
    # Everyone in the group, faker included.
    player_ids: list[str]
    # The one player in this group who doesn't know the keyword.
    faker_id: str
    # The secret word everyone except the faker is shown.
    keyword: str
    # Which phase this group is currently in.
    phase: str = GATHERING

    # gathering: players who have found their group.
    ready: set[str] = field(default_factory=set)
    # roles: players who have read their role.
    role_seen: set[str] = field(default_factory=set)

    # speaking: the order players say their word, and whose turn it is.
    speaking_order: list[str] = field(default_factory=list)
    current_speaker: int = 0

    # voting: non-faker voter ID -> suspected player ID, plus the faker's guess.
    votes: dict[str, str] = field(default_factory=dict)
    faker_guess: str | None = None

    # reveal: the outcome, computed once when the last answer comes in.
    result: dict | None = None

    @property
    def current_speaker_id(self) -> str | None:
        # The player whose turn it is to speak, or None outside the speaking phase.
        if self.phase != SPEAKING or self.current_speaker >= len(self.speaking_order):
            return None
        return self.speaking_order[self.current_speaker]

    def has_submitted(self, player_id: str) -> bool:
        # The faker submits a keyword guess; everyone else submits a vote.
        if player_id == self.faker_id:
            return self.faker_guess is not None
        return player_id in self.votes

    def submitted_player_ids(self) -> list[str]:
        # Players who have answered in the voting phase, in group order.
        return [player_id for player_id in self.player_ids if self.has_submitted(player_id)]


class KeywordsGame:
    """
    One running Keywords game: every group in the session plus each player's name.
    A Session holds one of these while a Keywords game is running.
    """

    def __init__(self, groups: list[KeywordsGroup], names: dict[str, str]):
        self.groups = groups
        # Names are captured when the game starts so votes match what players saw.
        self.names = names
        # Lookup from player ID to that player's group, so actions don't search every group.
        self._group_by_player = {
            player_id: group for group in groups for player_id in group.player_ids
        }

    @classmethod
    def start(cls, players: dict[str, str]) -> KeywordsGame:
        # Split players (ID -> name) into groups and give each a faker and a keyword.
        player_ids = list(players)

        if len(player_ids) < MIN_PLAYERS:
            raise ValueError(f"Keywords needs at least {MIN_PLAYERS} players.")

        """
        Use the fewest groups that keep every group at or under the size limit.
        Dealing players round-robin keeps sizes within one of each other, and every
        group has at least three players whenever there are at least three players.
        """
        group_count = ceil(len(player_ids) / MAX_GROUP_SIZE)

        # Each group needs its own keyword.
        if group_count > len(KEYWORDS):
            raise ValueError("There are not enough keywords for this many groups.")

        # Shuffle so groups are random rather than in join order.
        random.shuffle(player_ids)
        # A different keyword per group, so overhearing another table doesn't help a faker.
        keywords = random.sample(KEYWORDS, group_count)

        groups = []
        for index in range(group_count):
            # Every group_count-th player starting at index, i.e. dealing cards around a table.
            members = player_ids[index::group_count]
            # Cycle through the colors; past 8 groups, colors repeat as "Red 2", "Blue 2", ...
            color = GROUP_COLORS[index % len(GROUP_COLORS)]
            repeat = index // len(GROUP_COLORS)
            groups.append(KeywordsGroup(
                index=index,
                color=color,
                label=color if repeat == 0 else f"{color} {repeat + 1}",
                player_ids=members,
                faker_id=random.choice(members),
                keyword=keywords[index],
            ))

        return cls(groups, dict(players))

    @property
    def is_finished(self) -> bool:
        # The game is over once every group has reached the reveal.
        return all(group.phase == REVEAL for group in self.groups)

    def group_for(self, player_id: str) -> KeywordsGroup:
        # Find the player's group, or raise if they aren't in this game.
        group = self._group_by_player.get(player_id)
        if group is None:
            raise ValueError("You are not in a group for this game.")
        return group

    def _group_in_phase(self, player_id: str, phase: str) -> KeywordsGroup:
        # Find the player's group and make sure it is in the phase this action belongs to.
        group = self.group_for(player_id)
        if group.phase != phase:
            raise ValueError(f"Your group is not in the {phase} phase.")
        return group

    def mark_ready(self, player_id: str) -> KeywordsGroup:
        # Gathering: the player has found their group. Advances once everyone has.
        group = self._group_in_phase(player_id, GATHERING)
        group.ready.add(player_id)

        # ">=" is a superset check: every member of the group is in the ready set.
        if group.ready >= set(group.player_ids):
            group.phase = ROLES

        return group

    def mark_role_seen(self, player_id: str) -> KeywordsGroup:
        # Roles: the player has read their role. Advances once everyone has.
        group = self._group_in_phase(player_id, ROLES)
        group.role_seen.add(player_id)

        if group.role_seen >= set(group.player_ids):
            # Speaking order is a random shuffle of the group, chosen as speaking begins.
            group.speaking_order = random.sample(group.player_ids, len(group.player_ids))
            group.current_speaker = 0
            group.phase = SPEAKING

        return group

    def mark_word_said(self, player_id: str) -> KeywordsGroup:
        # Speaking: the current speaker has said their word out loud.
        group = self._group_in_phase(player_id, SPEAKING)

        # Only the player whose turn it is can end the turn.
        if group.current_speaker_id != player_id:
            raise ValueError("It isn't your turn to speak.")

        group.current_speaker += 1

        # After the last speaker, the group moves on to voting.
        if group.current_speaker >= len(group.speaking_order):
            group.phase = VOTING

        return group

    def submit_answer(self, player_id: str, text: str) -> KeywordsGroup:
        """
        Voting: a non-faker names a suspect; the faker guesses the keyword.
        Both go through the same call with the same input, so nothing about the
        request reveals who the faker is.
        """
        group = self._group_in_phase(player_id, VOTING)

        # One answer per player; the first one stands.
        if group.has_submitted(player_id):
            raise ValueError("You already submitted your answer.")

        # Tidy up spacing before checking length, so extra spaces don't count against the limit.
        answer = " ".join(text.split())
        if not answer:
            raise ValueError("Answer cannot be empty.")
        if len(answer) > MAX_ANSWER_LENGTH:
            raise ValueError(f"Answer cannot exceed {MAX_ANSWER_LENGTH} characters.")

        # The same text means a keyword guess from the faker and a suspect's name from anyone else.
        if player_id == group.faker_id:
            group.faker_guess = answer
        else:
            group.votes[player_id] = self._match_member(group, player_id, answer)

        # The last answer in decides the outcome and moves the group to the reveal.
        if all(group.has_submitted(member) for member in group.player_ids):
            group.result = self._resolve(group)
            group.phase = REVEAL

        return group

    def _match_member(self, group: KeywordsGroup, voter_id: str, answer: str) -> str:
        # Return the ID of the group member whose name was typed, ignoring case and spacing.
        typed = normalize(answer)

        for member_id in group.player_ids:
            if normalize(self.names.get(member_id, "")) == typed:
                if member_id == voter_id:
                    raise ValueError("You can't vote for yourself.")
                return member_id

        # Names are unique within a session, so no match means a typo or someone outside the group.
        raise ValueError(f'No one in your group is named "{answer}".')

    def _resolve(self, group: KeywordsGroup) -> dict:
        # Tally the votes and decide who won. Called once, when the last answer comes in.

        # Start every member at zero so the reveal can show members nobody voted for.
        vote_counts = {member_id: 0 for member_id in group.player_ids}
        for suspect_id in group.votes.values():
            vote_counts[suspect_id] += 1

        # The faker is caught only with strictly the most votes; a tie lets them escape.
        faker_votes = vote_counts[group.faker_id]
        caught = faker_votes > 0 and all(
            count < faker_votes
            for member_id, count in vote_counts.items()
            if member_id != group.faker_id
        )
        # The faker's guess counts if it matches the keyword, ignoring case and spacing.
        guessed = group.faker_guess is not None and normalize(group.faker_guess) == normalize(group.keyword)

        return {
            # Players win only by catching the faker AND the faker missing the word.
            "winner": "players" if caught and not guessed else "faker",
            "faker_id": group.faker_id,
            "faker_name": self.names.get(group.faker_id, ""),
            "keyword": group.keyword,
            "faker_guess": group.faker_guess,
            "faker_caught": caught,
            "faker_guessed_keyword": guessed,
            "vote_counts": vote_counts,
        }

    def _members(self, group: KeywordsGroup) -> list[dict]:
        # The group's members as ID/name pairs, for displaying on screen.
        return [
            {"player_id": member_id, "name": self.names.get(member_id, "")}
            for member_id in group.player_ids
        ]

    def player_view(self, player_id: str) -> dict:
        """
        Everything one player is allowed to see. Never send this to anyone else,
        because it contains that player's role and, unless they're the faker, the keyword.
        """
        group = self.group_for(player_id)
        # Roles stay hidden until the group has gathered and reaches the roles screen.
        role_known = group.phase != GATHERING
        is_faker = role_known and player_id == group.faker_id

        return {
            "phase": group.phase,
            "group_index": group.index,
            "group_color": group.color,
            "group_label": group.label,
            "members": self._members(group),
            # Who has readied up and read their role isn't secret; it shows progress.
            "ready_player_ids": sorted(group.ready),
            "role_seen_player_ids": sorted(group.role_seen),
            "is_faker": is_faker,
            # The faker always gets None here; that's the whole game.
            "keyword": group.keyword if role_known and not is_faker else None,
            "speaking_order": list(group.speaking_order),
            "current_speaker_id": group.current_speaker_id,
            # Only a count of who has voted, never what anyone answered.
            "has_submitted": group.has_submitted(player_id),
            "submitted_count": len(group.submitted_player_ids()),
            # The outcome is only shared once the group reaches the reveal.
            "result": group.result if group.phase == REVEAL else None,
        }

    def host_view(self) -> dict:
        # Full state of every group, including keywords and fakers. Host-only.
        return {
            "finished": self.is_finished,
            "groups": [
                {
                    "group_index": group.index,
                    "group_color": group.color,
                    "group_label": group.label,
                    "phase": group.phase,
                    "members": self._members(group),
                    "keyword": group.keyword,
                    "faker_id": group.faker_id,
                    "ready_player_ids": sorted(group.ready),
                    "role_seen_player_ids": sorted(group.role_seen),
                    "speaking_order": list(group.speaking_order),
                    "current_speaker_id": group.current_speaker_id,
                    "submitted_player_ids": group.submitted_player_ids(),
                    "result": group.result,
                }
                for group in self.groups
            ],
        }
