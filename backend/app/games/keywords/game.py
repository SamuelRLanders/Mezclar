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

MIN_PLAYERS = 3
MAX_GROUP_SIZE = 6
MAX_ANSWER_LENGTH = 50

GROUP_COLORS = ["Red", "Blue", "Green", "Yellow", "Purple", "Orange", "Pink", "Teal"]

GATHERING = "gathering"
ROLES = "roles"
SPEAKING = "speaking"
VOTING = "voting"
REVEAL = "reveal"


def normalize(text: str) -> str:
    """Collapse whitespace and ignore case so "  ice  CREAM " matches "Ice Cream"."""
    return " ".join(text.split()).casefold()


@dataclass
class KeywordsGroup:
    index: int
    color: str
    label: str
    player_ids: list[str]
    faker_id: str
    keyword: str
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
        if self.phase != SPEAKING or self.current_speaker >= len(self.speaking_order):
            return None
        return self.speaking_order[self.current_speaker]

    def has_submitted(self, player_id: str) -> bool:
        if player_id == self.faker_id:
            return self.faker_guess is not None
        return player_id in self.votes

    def submitted_player_ids(self) -> list[str]:
        return [player_id for player_id in self.player_ids if self.has_submitted(player_id)]


class KeywordsGame:
    def __init__(self, groups: list[KeywordsGroup], names: dict[str, str]):
        self.groups = groups
        # Names are captured when the game starts so votes match what players saw.
        self.names = names
        self._group_by_player = {
            player_id: group for group in groups for player_id in group.player_ids
        }

    @classmethod
    def start(cls, players: dict[str, str]) -> KeywordsGame:
        # Split players (ID -> name) into groups and give each a faker and a keyword.
        player_ids = list(players)

        if len(player_ids) < MIN_PLAYERS:
            raise ValueError(f"Keywords needs at least {MIN_PLAYERS} players.")

        # Fewest groups that keep every group at or under the size limit. Dealing
        # players round-robin keeps sizes within one of each other, and every group
        # has at least three players whenever there are at least three players.
        group_count = ceil(len(player_ids) / MAX_GROUP_SIZE)

        if group_count > len(KEYWORDS):
            raise ValueError("There are not enough keywords for this many groups.")

        random.shuffle(player_ids)
        # A different keyword per group, so overhearing another table doesn't help a faker.
        keywords = random.sample(KEYWORDS, group_count)

        groups = []
        for index in range(group_count):
            members = player_ids[index::group_count]
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
        return all(group.phase == REVEAL for group in self.groups)

    def group_for(self, player_id: str) -> KeywordsGroup:
        group = self._group_by_player.get(player_id)
        if group is None:
            raise ValueError("You are not in a group for this game.")
        return group

    def _group_in_phase(self, player_id: str, phase: str) -> KeywordsGroup:
        group = self.group_for(player_id)
        if group.phase != phase:
            raise ValueError(f"Your group is not in the {phase} phase.")
        return group

    def mark_ready(self, player_id: str) -> KeywordsGroup:
        """Gathering: the player has found their group."""
        group = self._group_in_phase(player_id, GATHERING)
        group.ready.add(player_id)

        if group.ready >= set(group.player_ids):
            group.phase = ROLES

        return group

    def mark_role_seen(self, player_id: str) -> KeywordsGroup:
        """Roles: the player has read their role and is ready to play."""
        group = self._group_in_phase(player_id, ROLES)
        group.role_seen.add(player_id)

        if group.role_seen >= set(group.player_ids):
            group.speaking_order = random.sample(group.player_ids, len(group.player_ids))
            group.current_speaker = 0
            group.phase = SPEAKING

        return group

    def mark_word_said(self, player_id: str) -> KeywordsGroup:
        """Speaking: the current speaker has said their word out loud."""
        group = self._group_in_phase(player_id, SPEAKING)

        if group.current_speaker_id != player_id:
            raise ValueError("It isn't your turn to speak.")

        group.current_speaker += 1

        if group.current_speaker >= len(group.speaking_order):
            group.phase = VOTING

        return group

    def submit_answer(self, player_id: str, text: str) -> KeywordsGroup:
        """Voting: a non-faker names a suspect; the faker guesses the keyword.

        Both go through the same call with the same input, so nothing about the
        request reveals who the faker is.
        """
        group = self._group_in_phase(player_id, VOTING)

        if group.has_submitted(player_id):
            raise ValueError("You already submitted your answer.")

        answer = " ".join(text.split())
        if not answer:
            raise ValueError("Answer cannot be empty.")
        if len(answer) > MAX_ANSWER_LENGTH:
            raise ValueError(f"Answer cannot exceed {MAX_ANSWER_LENGTH} characters.")

        if player_id == group.faker_id:
            group.faker_guess = answer
        else:
            group.votes[player_id] = self._match_member(group, player_id, answer)

        if all(group.has_submitted(member) for member in group.player_ids):
            group.result = self._resolve(group)
            group.phase = REVEAL

        return group

    def _match_member(self, group: KeywordsGroup, voter_id: str, answer: str) -> str:
        """Return the ID of the group member whose name was typed."""
        typed = normalize(answer)

        for member_id in group.player_ids:
            if normalize(self.names.get(member_id, "")) == typed:
                if member_id == voter_id:
                    raise ValueError("You can't vote for yourself.")
                return member_id

        raise ValueError(f'No one in your group is named "{answer}".')

    def _resolve(self, group: KeywordsGroup) -> dict:
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
        guessed = group.faker_guess is not None and normalize(group.faker_guess) == normalize(group.keyword)

        return {
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
        return [
            {"player_id": member_id, "name": self.names.get(member_id, "")}
            for member_id in group.player_ids
        ]

    def player_view(self, player_id: str) -> dict:
        """Everything one player is allowed to see. Never send this to anyone else."""
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
            "ready_player_ids": sorted(group.ready),
            "role_seen_player_ids": sorted(group.role_seen),
            "is_faker": is_faker,
            "keyword": group.keyword if role_known and not is_faker else None,
            "speaking_order": list(group.speaking_order),
            "current_speaker_id": group.current_speaker_id,
            "has_submitted": group.has_submitted(player_id),
            "submitted_count": len(group.submitted_player_ids()),
            "result": group.result if group.phase == REVEAL else None,
        }

    def host_view(self) -> dict:
        """Full state of every group, including secrets. Host-only."""
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
