import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from backend.app.api import routes_host
from backend.app.api.voting import start_voting
from backend.app.sessions import registry


@pytest.fixture
def clock(monkeypatch):
    clock = Mock(wraps=datetime)
    clock.now.return_value = datetime(2026, 11, 3, tzinfo=timezone.utc)
    monkeypatch.setattr(routes_host, "datetime", clock)
    monkeypatch.setattr("backend.app.sessions.session.datetime", clock)
    return clock


@pytest.fixture
def running_game(client, clock):
    created = client.post("/session").json()
    code = created["session_id"]
    for player_id in ["first", "second"]:
        client.post(f"/session/{code}/join", json={"player_id": player_id, "name": player_id})
    assert client.post(f"/session/{code}/start", json={
        "game_id": "quiplash", "minimum_players": 2, "maximum_players": 4,
    }).status_code == 200
    return code, {"X-Host-Token": created["host_token"]}, registry.get_session(code)


def test_pause_freezes_time_and_resume_keeps_answers(client, running_game, clock):
    code, headers, session = running_game
    client.post(f"/session/{code}/start-timer", headers=headers, json={"duration_seconds": 60})
    session.submit_answer("first", "Keep this answer")
    clock.now.return_value += timedelta(seconds=12.5)
    assert client.post(f"/session/{code}/control", headers=headers, json={"action": "pause", "current_round": 1}).status_code == 200
    assert session.round_deadline is None
    assert session.paused_remaining == 47.5
    clock.now.return_value += timedelta(seconds=100)
    assert client.post(f"/session/{code}/submit-answer", json={"player_id": "second", "answer": "paused"}).status_code == 400
    assert client.post(f"/session/{code}/control", headers=headers, json={"action": "resume", "current_round": 1}).status_code == 200
    assert session.round_deadline == clock.now.return_value + timedelta(seconds=47.5)
    assert session.game_paused is False
    group = session.get_player_group_index(1, "first")
    assert session.group_answers[1][group]["first"] == "Keep this answer"


@pytest.mark.parametrize("paused", [False, True])
def test_extend_adds_thirty_seconds_without_losing_answers(client, running_game, clock, paused):
    code, headers, session = running_game
    client.post(f"/session/{code}/start-timer", headers=headers, json={"duration_seconds": 60})
    session.submit_answer("first", "Keep this answer")
    clock.now.return_value += timedelta(seconds=7.25)
    if paused:
        client.post(f"/session/{code}/control", headers=headers, json={"action": "pause", "current_round": 1})
    before = session.paused_remaining if paused else session.round_deadline
    assert client.post(f"/session/{code}/control", headers=headers, json={"action": "extend", "current_round": 1}).status_code == 200
    assert (session.paused_remaining if paused else session.round_deadline) == before + (30 if paused else timedelta(seconds=30))
    assert session.game_paused is paused
    assert session.response_progress()["submitted_player_ids"] == ["first"]


def test_skip_resets_the_timer_and_rejects_stale_requests(client, running_game, clock):
    code, headers, session = running_game
    client.post(f"/session/{code}/start-timer", headers=headers, json={"duration_seconds": 60})
    session.submit_answer("first", "Old answer")
    client.post(f"/session/{code}/control", headers=headers, json={"action": "pause", "current_round": 1})
    assert client.post(f"/session/{code}/control", headers=headers, json={"action": "skip", "current_round": 1}).status_code == 200
    assert session.current_round == 2
    assert session.game_paused is False
    assert session.round_deadline == clock.now.return_value + timedelta(seconds=60)
    assert session.response_progress()["submitted_count"] == 0
    assert session.group_answers[1]
    assert client.post(f"/session/{code}/control", headers=headers, json={"action": "skip", "current_round": 1}).status_code == 400
    assert client.post(f"/session/{code}/submit-answer", json={
        "player_id": "first", "answer": "late", "current_round": 1,
    }).status_code == 400
    assert client.post(f"/session/{code}/start-timer", headers=headers, json={
        "duration_seconds": 60, "current_round": 1,
    }).status_code == 400


def test_expired_round_rejects_answers_before_timer_task_runs(client, running_game, clock):
    code, headers, session = running_game
    session.round_deadline = clock.now.return_value - timedelta(seconds=1)
    assert client.post(f"/session/{code}/submit-answer", json={"player_id": "first", "answer": "late"}).status_code == 400
    for action in ["pause", "extend"]:
        assert client.post(f"/session/{code}/control", headers=headers, json={"action": action, "current_round": 1}).status_code == 400
    assert session.response_progress()["submitted_count"] == 0


def test_skip_stops_sending_old_voting_options(running_game, monkeypatch):
    _, _, session = running_game

    async def skip_round(*args):
        session.advance_round()

    send = AsyncMock(side_effect=skip_round)
    monkeypatch.setattr("backend.app.api.voting.connection_manager.send_to_player", send)
    asyncio.run(start_voting(session, 1))
    assert send.await_count == 1
    assert session.current_round == 2
    assert session.phase == "answering"


@pytest.mark.parametrize("final_round", [False, True])
def test_timer_expiry_starts_voting_without_counting_placeholders(running_game, clock, final_round):
    _, _, session = running_game
    if final_round:
        session.current_round = session.total_rounds
    session.submit_answer("first", "Actual answer")
    session.round_deadline = clock.now.return_value
    asyncio.run(routes_host.run_round_timer(session, session.current_round, session.round_deadline))
    assert session.phase == "voting"
    assert session.current_round == (session.total_rounds if final_round else 1)
    assert session.round_deadline is None
    assert session.response_progress()["submitted_count"] == 1
    group = session.get_player_group_index(session.current_round, "second")
    assert session.group_answers[session.current_round][group]["second"] == "No answer submitted (time expired)"


@pytest.mark.parametrize("token", [None, "wrong-token", "first", b"\xff"])
def test_players_cannot_use_controls_or_timer_endpoints(client, running_game, token):
    code, _, _ = running_game
    headers = {} if token is None else {"X-Host-Token": token}
    before = client.get(f"/session/{code}").json()
    for action in ["pause", "resume", "skip", "extend"]:
        assert client.post(f"/session/{code}/control", headers=headers, json={"action": action, "current_round": 1}).status_code == 403
    assert client.post(f"/session/{code}/advance-round", headers=headers).status_code == 403
    assert client.post(f"/session/{code}/start-timer", headers=headers, json={"duration_seconds": 60}).status_code == 403
    assert client.get(f"/session/{code}").json() == before


def test_host_token_is_private_and_specific_to_its_session(client, running_game):
    code, headers, _ = running_game
    other = client.post("/session").json()
    assert "host_token" not in client.get(f"/session/{code}").json()
    assert client.post(f"/session/{code}/control", headers={"X-Host-Token": other["host_token"]}, json={"action": "pause", "current_round": 1}).status_code == 403
    with client.websocket_connect(f"/ws/session/{code}/player/first") as socket:
        for _ in range(4):
            assert headers["X-Host-Token"] not in str(socket.receive_json())


def test_invalid_controls_and_pause_without_a_timer(client, running_game):
    code, headers, session = running_game
    for body in [{}, {"action": "unknown", "current_round": 1}, {"action": "skip", "current_round": 0}, {"action": "skip", "current_round": 1, "player_id": "first"}]:
        assert client.post(f"/session/{code}/control", headers=headers, json=body).status_code == 422
    for action, status in [("resume", 400), ("extend", 400), ("pause", 200), ("pause", 400), ("resume", 200)]:
        assert client.post(f"/session/{code}/control", headers=headers, json={"action": action, "current_round": 1}).status_code == status
    assert session.round_deadline is None
    assert session.game_paused is False


def test_controls_reject_closed_games_and_only_skip_during_voting(client, running_game):
    code, headers, session = running_game
    idle = client.post("/session").json()
    for action in ["pause", "resume", "extend", "skip"]:
        assert client.post(f"/session/{idle['session_id']}/control", headers={
            "X-Host-Token": idle["host_token"],
        }, json={"action": action, "current_round": 1}).status_code == 400
    for phase in ["finished", "voting"]:
        session.phase = phase
        for action in ["pause", "resume", "extend"] + ([] if phase == "voting" else ["skip"]):
            assert client.post(f"/session/{code}/control", headers=headers, json={"action": action, "current_round": 1}).status_code == 400
        assert client.post(f"/session/{code}/start-timer", headers=headers, json={"duration_seconds": 60}).status_code == 400
    assert client.post(f"/session/{code}/control", headers=headers, json={"action": "skip", "current_round": 1}).status_code == 200
    assert session.current_round == 2


def test_controls_update_players_and_restore_paused_state(client, running_game):
    code, headers, session = running_game
    client.post(f"/session/{code}/start-timer", headers=headers, json={"duration_seconds": 60})
    with client.websocket_connect(f"/ws/session/{code}/player/first") as first:
        for _ in range(4):
            first.receive_json()
        with client.websocket_connect(f"/ws/session/{code}/player/second") as second:
            for _ in range(4):
                second.receive_json()
            first.receive_json()
            for action in ["pause", "extend", "resume", "skip", "pause"]:
                assert client.post(f"/session/{code}/control", headers=headers, json={"action": action, "current_round": session.current_round}).status_code == 200
                for socket in [first, second]:
                    message = socket.receive_json()
                    while message["type"] != "round_updated":
                        message = socket.receive_json()
                    assert message["game_paused"] == session.game_paused
                    assert message["current_round"] == session.current_round
    with client.websocket_connect(f"/ws/session/{code}/player/first") as socket:
        assert socket.receive_json()["type"] == "connected"
        assert client.get(f"/session/{code}").json()["game_paused"] is True
