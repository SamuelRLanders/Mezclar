import asyncio
from unittest.mock import AsyncMock, patch

from backend.app.api.voting import start_voting
from backend.app.sessions import registry
from backend.app.sessions.session import Session


def start_quiplash(client, rounds=3):
    """Four players and three rounds always make two groups of two."""
    code = client.post("/session", json={"settings": {"rounds": rounds}}).json()["session_id"]
    for player_id in ["p1", "p2", "p3", "p4"]:
        client.post("/session/" + code + "/join", json={"player_id": player_id, "name": player_id})
    client.post("/session/" + code + "/start", json={
        "game_id": "quiplash", "minimum_players": 2, "maximum_players": 10,
    })
    return code

def submit(client, code, player_id):
    return client.post("/session/" + code + "/submit-answer", json={
        "player_id": player_id, "answer": "answer from " + player_id,
    })

def kick(client, code, player_id):
    return client.post("/session/" + code + "/kick", json={"player_id": player_id})

def join(client, code, player_id, device_token=None):
    return client.post("/session/" + code + "/join", json={
        "player_id": player_id, "name": player_id, "device_token": device_token,
    })

def everyone_submits(client, code):
    for player_id in list(registry.get_session(code).players):
        submit(client, code, player_id)

def ballots_sent(send_to_player):
    return {
        call.args[1]: call.args[2]
        for call in send_to_player.await_args_list
        if call.args[2]["type"] == "voting_started"
    }


def test_kicking_last_unsubmitted_player_starts_voting(client):
    code = start_quiplash(client)
    session = registry.get_session(code)
    target = session.round_groups[1][0][0]

    for player_id in ["p1", "p2", "p3", "p4"]:
        if player_id != target:
            submit(client, code, player_id)
    assert session.phase == "answering"

    kick(client, code, target)
    assert session.phase == "voting"

def test_kick_leaves_past_rounds_alone(client):
    code = start_quiplash(client)
    client.post("/session/" + code + "/advance-round")
    kick(client, code, "p1")

    session = registry.get_session(code)
    assert any("p1" in group for group in session.round_groups[1])
    assert all("p1" not in group for r in (2, 3) for group in session.round_groups[r])

def test_kicked_player_not_waited_on_in_later_rounds(client):
    code = start_quiplash(client)
    kick(client, code, "p1")
    client.post("/session/" + code + "/advance-round")

    everyone_submits(client, code)
    assert registry.get_session(code).phase == "voting"

def test_kick_during_voting_removes_answer_from_ballots(client):
    code = start_quiplash(client)
    everyone_submits(client, code)
    session = registry.get_session(code)
    target = session.round_groups[1][0][0]

    with patch(
        "backend.app.api.voting.connection_manager.send_to_player",
        new_callable=AsyncMock,
    ) as send_to_player:
        kick(client, code, target)

    assert all(target not in answers for answers in session.group_answers[1].values())

    ballots = ballots_sent(send_to_player)
    assert target not in ballots
    assert len(ballots) == 3
    for ballot in ballots.values():
        for group in ballot["groups"]:
            assert target not in [answer["player_id"] for answer in group["answers"]]

def test_kick_during_voting_does_not_resend_to_players_who_voted(client):
    code = start_quiplash(client)
    everyone_submits(client, code)
    session = registry.get_session(code)
    group_a, group_b = session.round_groups[1]

    client.post("/session/" + code + "/submit-vote", json={
        "voter_id": group_b[0], "group_index": 0, "answer_owner_id": group_a[1],
    })

    with patch(
        "backend.app.api.voting.connection_manager.send_to_player",
        new_callable=AsyncMock,
    ) as send_to_player:
        kick(client, code, group_a[0])

    assert group_b[0] not in ballots_sent(send_to_player)

def test_vote_for_kicked_player_is_ignored(client):
    code = start_quiplash(client)
    everyone_submits(client, code)
    session = registry.get_session(code)
    group_a, group_b = session.round_groups[1]
    target, teammate = group_a

    kick(client, code, target)

    ignored = client.post("/session/" + code + "/submit-vote", json={
        "voter_id": group_b[0], "group_index": 0, "answer_owner_id": target,
    })
    counted = client.post("/session/" + code + "/submit-vote", json={
        "voter_id": group_b[1], "group_index": 0, "answer_owner_id": teammate,
    })

    assert ignored.status_code == 200
    assert counted.status_code == 200
    assert session.group_votes[1][0] == {group_b[1]: teammate}
    assert session.scores.get(target, 0) == 0
    assert session.scores[teammate] == 1

def test_vote_for_unknown_player_still_rejected(client):
    code = start_quiplash(client)
    everyone_submits(client, code)
    voter = registry.get_session(code).round_groups[1][1][0]

    response = client.post("/session/" + code + "/submit-vote", json={
        "voter_id": voter, "group_index": 0, "answer_owner_id": "nobody",
    })
    assert response.status_code == 400

def test_emptied_group_left_out_of_ballots():
    session = Session("abc123", settings={"rounds": 3})
    session.configure_game("quiplash", 2, 50)
    for i in range(6):
        session.add_player(f"player{i}", f"Player {i}")
    session.start_game()

    for player_id in list(session.round_groups[1][0]):
        session.kick_player(player_id)
    for player_id in session.players:
        session.submit_answer(player_id, "an answer")

    with patch(
        "backend.app.api.voting.connection_manager.send_to_player",
        new_callable=AsyncMock,
    ) as send_to_player:
        asyncio.run(start_voting(session, 1))

    ballots = ballots_sent(send_to_player)
    assert len(ballots) == 4
    for ballot in ballots.values():
        assert 0 not in [group["group_index"] for group in ballot["groups"]]
        assert all(group["answers"] for group in ballot["groups"])

def test_join_stores_device_token(client):
    code = client.post("/session").json()["session_id"]
    join(client, code, "p1", "device-1")
    assert registry.get_session(code).get_player("p1").device_token == "device-1"

def test_kicked_device_cannot_rejoin_with_new_player_id(client):
    code = client.post("/session").json()["session_id"]
    join(client, code, "p1", "device-1")
    kick(client, code, "p1")

    response = join(client, code, "new-tab-id", "device-1")
    assert response.status_code == 403
    assert "removed" in response.json()["detail"]
    assert "new-tab-id" not in registry.get_session(code).players

def test_kicked_player_id_cannot_rejoin_without_token(client):
    code = client.post("/session").json()["session_id"]
    join(client, code, "p1", "device-1")
    kick(client, code, "p1")

    assert join(client, code, "p1").status_code == 403

def test_kicked_mid_game_cannot_rejoin(client):
    code = client.post("/session", json={"settings": {
        "options": {"allowLateJoin": True},
    }}).json()["session_id"]
    for player_id in ["p1", "p2", "p3"]:
        join(client, code, player_id, "device-" + player_id)
    client.post("/session/" + code + "/start", json={
        "game_id": "quiplash", "minimum_players": 2, "maximum_players": 10,
    })
    kick(client, code, "p1")

    assert join(client, code, "late-id", "device-p1").status_code == 403

def test_kicked_device_can_join_another_session(client):
    first = client.post("/session").json()["session_id"]
    second = client.post("/session").json()["session_id"]
    join(client, first, "p1", "device-1")
    kick(client, first, "p1")

    assert join(client, second, "p1", "device-1").status_code == 200

def test_other_devices_unaffected_by_kick(client):
    code = client.post("/session").json()["session_id"]
    join(client, code, "p1", "device-1")
    kick(client, code, "p1")

    assert join(client, code, "p2", "device-2").status_code == 200
