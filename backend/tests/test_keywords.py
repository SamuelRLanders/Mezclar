"""
Tests for the Keywords game.

The first four call KeywordsGame directly to check the game rules. The last two
go through the HTTP routes to check privacy and a full game from start to reveal.
"""

import pytest

from backend.app.games.keywords.game import KeywordsGame, KeywordsGroup
from backend.app.sessions import registry

# Four players always make exactly one group, which keeps the rule tests simple.
FOUR_PLAYERS = {"a": "Alice", "b": "Bob", "c": "Cara", "d": "Dan"}


def play_to_roles(names: dict[str, str]) -> tuple[KeywordsGame, KeywordsGroup]:
    # Start a game and have every player in the first group ready up.
    game = KeywordsGame.start(names)
    group = game.groups[0]
    for player_id in group.player_ids:
        game.mark_ready(player_id)
    return game, group


def play_to_voting(names: dict[str, str]) -> tuple[KeywordsGame, KeywordsGroup]:
    # Walk the first group through gathering, roles and speaking.
    game, group = play_to_roles(names)
    for player_id in group.player_ids:
        game.mark_role_seen(player_id)
    for player_id in list(group.speaking_order):
        game.mark_word_said(player_id)
    return game, group


@pytest.mark.parametrize("player_count", [3, 7, 13, 20])
def test_groups_balanced_with_one_faker_each(player_count):
    names = {f"p{i}": f"Player {i}" for i in range(player_count)}
    game = KeywordsGame.start(names)

    # Everyone is placed in exactly one group.
    placed = [player_id for group in game.groups for player_id in group.player_ids]
    assert sorted(placed) == sorted(names)

    # Every group is a playable size and its faker is one of its own members.
    for group in game.groups:
        assert 3 <= len(group.player_ids) <= 6
        assert group.faker_id in group.player_ids

    # No two groups share a keyword.
    keywords = [group.keyword for group in game.groups]
    assert len(set(keywords)) == len(keywords)


def test_faker_never_sees_keyword():
    game = KeywordsGame.start(FOUR_PLAYERS)
    group = game.groups[0]

    # While gathering, nobody has been told their role yet.
    for player_id in group.player_ids:
        view = game.player_view(player_id)
        assert view["is_faker"] is False
        assert view["keyword"] is None

    for player_id in group.player_ids:
        game.mark_ready(player_id)

    # On the roles screen, the faker learns their role but never the keyword.
    for player_id in group.player_ids:
        view = game.player_view(player_id)
        if player_id == group.faker_id:
            assert view["is_faker"] is True
            assert view["keyword"] is None
        else:
            assert view["is_faker"] is False
            assert view["keyword"] == group.keyword


def test_only_current_speaker_can_end_turn():
    game, group = play_to_roles(FOUR_PLAYERS)
    for player_id in group.player_ids:
        game.mark_role_seen(player_id)
    assert group.phase == "speaking"

    # The second speaker can't end the first speaker's turn.
    with pytest.raises(ValueError, match="your turn"):
        game.mark_word_said(group.speaking_order[1])

    # Once everyone has spoken in order, the group moves on to voting.
    for player_id in list(group.speaking_order):
        game.mark_word_said(player_id)
    assert group.phase == "voting"


@pytest.mark.parametrize("scenario, guess_right, winner", [
    ("caught", False, "players"),  # everyone accuses the faker, who guesses wrong
    ("caught", True, "faker"),     # everyone accuses the faker, but they guess the word
    ("tie", False, "faker"),       # votes split 1-1-1, so the faker escapes
])
def test_reveal_outcomes(scenario, guess_right, winner):
    game, group = play_to_voting(FOUR_PLAYERS)
    first, second, third = [p for p in group.player_ids if p != group.faker_id]

    if scenario == "caught":
        votes = {first: group.faker_id, second: group.faker_id, third: group.faker_id}
    else:
        # The faker, second and third each get exactly one vote.
        votes = {first: group.faker_id, second: third, third: second}

    for voter_id, suspect_id in votes.items():
        game.submit_answer(voter_id, game.names[suspect_id])
    game.submit_answer(group.faker_id, group.keyword if guess_right else "definitely wrong")

    assert group.phase == "reveal"
    assert group.result["winner"] == winner


@pytest.fixture
def keywords_game(client):
    # A running Keywords game with four players, through the real routes.
    created = client.post("/session").json()
    code = created["session_id"]
    for player_id, name in FOUR_PLAYERS.items():
        client.post(f"/session/{code}/join", json={"player_id": player_id, "name": name})
    assert client.post(f"/session/{code}/start", json={
        "game_id": "keywords", "minimum_players": 3, "maximum_players": 10,
    }).status_code == 200
    return code, {"X-Host-Token": created["host_token"]}


def test_secrets_stay_private_over_api(client, keywords_game):
    code, host_headers = keywords_game
    group = registry.get_session(code).keywords.groups[0]

    # The public session info, which any player can fetch, never mentions the keyword.
    assert group.keyword not in client.get(f"/session/{code}").text

    # The host view holds the secrets, so it needs the host token.
    assert client.get(f"/session/{code}/keywords/host-state").status_code == 403
    response = client.get(f"/session/{code}/keywords/host-state", headers=host_headers)
    assert response.status_code == 200
    assert response.json()["groups"][0]["keyword"] == group.keyword


def test_full_game_over_api(client, keywords_game):
    code, host_headers = keywords_game

    # Nobody can join once the groups are set.
    late = client.post(f"/session/{code}/join", json={"player_id": "late", "name": "Late"})
    assert late.status_code == 403

    for player_id in FOUR_PLAYERS:
        assert client.post(f"/session/{code}/keywords/ready", json={"player_id": player_id}).status_code == 200
    for player_id in FOUR_PLAYERS:
        assert client.post(f"/session/{code}/keywords/role-seen", json={"player_id": player_id}).status_code == 200

    # The speaking order is shuffled, so read it from the host view.
    group = client.get(f"/session/{code}/keywords/host-state", headers=host_headers).json()["groups"][0]
    for player_id in group["speaking_order"]:
        assert client.post(f"/session/{code}/keywords/word-said", json={"player_id": player_id}).status_code == 200

    # Everyone accuses the faker; the faker guesses wrong.
    faker_id = group["faker_id"]
    for player_id in FOUR_PLAYERS:
        text = "definitely wrong" if player_id == faker_id else FOUR_PLAYERS[faker_id]
        response = client.post(f"/session/{code}/keywords/submit", json={"player_id": player_id, "text": text})
        assert response.status_code == 200

    # The last submit returns that player's view, now showing the reveal.
    view = response.json()
    assert view["phase"] == "reveal"
    assert view["result"]["winner"] == "players"
    assert registry.get_session(code).phase == "finished"
