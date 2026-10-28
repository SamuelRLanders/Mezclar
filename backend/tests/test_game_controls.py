import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from backend.app.games import timer
from backend.app.games.quiplash.prompts import QUIPLASH_PROMPTS
from backend.app.sessions import registry
from backend.app.sessions.session import Session


@pytest.fixture
def clock(monkeypatch):
    clock = Mock(return_value=100.0)
    monkeypatch.setattr("backend.app.sessions.session.monotonic", clock)
    return clock


@pytest.fixture
def game(clock):
    game = Session("TEST")
    game.add_player("first", "Casey")
    game.configure_game("quiplash", 1, 4)
    game.start_game()
    return game


@pytest.fixture
def running_game(client, clock):
    created = client.post("/session").json()
    code = created["session_id"]
    for player_id, name in [("first", "Casey"), ("second", "Taylor")]:
        client.post(f"/session/{code}/join", json={"player_id": player_id, "name": name})
    assert client.post(f"/session/{code}/start", json={
        "game_id": "quiplash", "minimum_players": 1, "maximum_players": 4,
    }).status_code == 200
    return code, {"X-Host-Token": created["host_token"]}


def test_pause_freezes_time_and_resume_keeps_answers(game, clock):
    game.submit_answer("first", "Keep this answer", 1)
    clock.return_value = 112.5
    game.control_game("pause", 1)
    assert game.remaining_seconds == 47.5
    clock.return_value = 200.0
    assert game.remaining_seconds == 47.5
    with pytest.raises(ValueError):
        game.submit_answer("first", "Not while paused", 1)
    game.control_game("resume", 1)
    clock.return_value = 210.0
    assert game.remaining_seconds == 37.5
    assert game.answers == {"first": "Keep this answer"}


@pytest.mark.parametrize("paused", [False, True])
def test_extend_adds_exactly_thirty_seconds_without_losing_answers(game, clock, paused):
    game.submit_answer("first", "Keep this answer", 1)
    clock.return_value = 107.25
    if paused:
        game.control_game("pause", 1)
    before = game.remaining_seconds
    game.control_game("extend", 1)
    assert game.remaining_seconds == before + 30
    assert game.game_paused is paused
    assert game.answers == {"first": "Keep this answer"}


def test_skip_resets_the_round_and_rejects_stale_answers(game):
    game.submit_answer("first", "Old answer", 1)
    game.control_game("pause", 1)
    game.control_game("skip", 1)
    assert game.current_round == 2
    assert game.current_prompt == QUIPLASH_PROMPTS[1]
    assert game.remaining_seconds == 60
    assert game.game_paused is False
    assert game.answers == {}
    with pytest.raises(ValueError):
        game.submit_answer("first", "Late old answer", 1)
    with pytest.raises(ValueError):
        game.control_game("skip", 1)


def test_expired_round_rejects_answers_before_the_timer_worker_runs(game, clock):
    clock.return_value = 160.0
    with pytest.raises(ValueError):
        game.submit_answer("first", "Too late", 1)
    for action in ["pause", "extend"]:
        with pytest.raises(ValueError):
            game.control_game(action, 1)
    assert game.answers == {}


@pytest.mark.parametrize("final_round", [False, True])
def test_timer_expiry_advances_or_completes_without_a_host_request(game, clock, monkeypatch, final_round):
    if final_round:
        game.current_round = len(QUIPLASH_PROMPTS)
        game.current_prompt = QUIPLASH_PROMPTS[-1]
    registry._sessions[game.session_id] = game
    clock.return_value = 160.0
    notification = AsyncMock(side_effect=asyncio.CancelledError)
    monkeypatch.setattr(timer, "broadcast_round", notification)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(asyncio.wait_for(timer.run_round_timers(), timeout=1))
    notification.assert_awaited_once_with(game)
    assert game.game_completed is final_round
    assert game.remaining_seconds == (0 if final_round else 60)
    assert game.current_round == (len(QUIPLASH_PROMPTS) if final_round else 2)
    if final_round:
        assert game.round_deadline is None


@pytest.mark.parametrize("token", [None, "wrong-token", "first", b"\xff"])
def test_players_cannot_control_the_game_or_use_legacy_advance(client, running_game, token):
    code, _ = running_game
    headers = {} if token is None else {"X-Host-Token": token}
    before = client.get(f"/session/{code}").json()
    for action in ["pause", "resume", "skip", "extend"]:
        response = client.post(f"/session/{code}/control", headers=headers, json={
            "action": action, "current_round": 1,
        })
        assert response.status_code == 403
    assert client.post(f"/session/{code}/advance-round", headers=headers).status_code == 403
    assert client.get(f"/session/{code}").json() == before


def test_host_token_is_private_and_cannot_control_another_session(client, running_game):
    code, headers = running_game
    other = client.post("/session").json()
    assert "host_token" not in client.get(f"/session/{code}").json()
    assert client.post(f"/session/{code}/control", headers={"X-Host-Token": other["host_token"]}, json={
        "action": "pause", "current_round": 1,
    }).status_code == 403
    with client.websocket_connect(f"/ws/session/{code}/player/first") as socket:
        assert headers["X-Host-Token"] not in str(socket.receive_json())
        assert headers["X-Host-Token"] not in str(socket.receive_json())


def test_invalid_controls_and_paused_submissions_are_rejected(client, running_game):
    code, headers = running_game
    for body in [
        {}, {"action": "unknown", "current_round": 1}, {"action": "skip", "current_round": 0},
        {"action": "skip", "current_round": 1, "player_id": "first"},
    ]:
        assert client.post(f"/session/{code}/control", headers=headers, json=body).status_code == 422
    for action, status in [("resume", 400), ("pause", 200), ("pause", 400), ("resume", 200)]:
        response = client.post(f"/session/{code}/control", headers=headers, json={"action": action, "current_round": 1})
        assert response.status_code == status
    assert client.post(f"/session/{code}/control", headers=headers, json={"action": "pause", "current_round": 1}).status_code == 200
    assert client.post(f"/session/{code}/submit-answer", json={
        "player_id": "first", "answer": "Not while paused", "current_round": 1,
    }).status_code == 400


def test_controls_reject_games_before_start_and_after_completion(game):
    idle = Session("IDLE")
    for action in ["pause", "resume", "skip", "extend"]:
        with pytest.raises(ValueError):
            idle.control_game(action, 1)
    for round_number in range(1, len(QUIPLASH_PROMPTS) + 1):
        game.control_game("skip", round_number)
    assert game.game_completed is True
    for action in ["pause", "resume", "skip", "extend"]:
        with pytest.raises(ValueError):
            game.control_game(action, game.current_round)


def test_controls_update_connected_players_and_restore_paused_state(client, running_game):
    code, headers = running_game
    with client.websocket_connect(f"/ws/session/{code}/player/first") as first:
        first.receive_json()
        first.receive_json()
        with client.websocket_connect(f"/ws/session/{code}/player/second") as second:
            second.receive_json()
            second.receive_json()
            first.receive_json()
            for action in ["pause", "extend", "resume", "skip", "pause"]:
                state = client.get(f"/session/{code}").json()
                response = client.post(f"/session/{code}/control", headers=headers, json={
                    "action": action, "current_round": state["current_round"],
                })
                assert response.status_code == 200
                message = first.receive_json()
                assert message == second.receive_json()
                assert message["type"] == "round_updated"
                for field in ["current_round", "game_paused", "remaining_seconds"]:
                    assert message[field] == response.json()[field]

    with client.websocket_connect(f"/ws/session/{code}/player/first") as socket:
        socket.receive_json()
        socket.receive_json()
        assert client.get(f"/session/{code}").json()["game_paused"] is True
