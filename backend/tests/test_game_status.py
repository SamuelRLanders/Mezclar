import json

import anyio
import pytest


def test_start_requires_enough_players(client):
    code = client.post("/session").json()["session_id"]
    response = client.post("/session/" + code + "/start", json={
        "game_id": "test-game", "minimum_players": 2, "maximum_players": 4,
    })
    assert response.status_code == 400
    assert client.get("/session/" + code).json()["game_started"] is False

def test_start_game_status_survives_lobby_polling(client):
    code = client.post("/session").json()["session_id"]
    for player_id in ["first", "second"]:
        client.post("/session/" + code + "/join", json={"player_id": player_id, "name": player_id})
    payload = {"game_id": "test-game", "minimum_players": 2, "maximum_players": 4}
    response = client.post("/session/" + code + "/start", json=payload)
    assert response.status_code == 200
    assert response.json()["game_started"] is True
    session = client.get("/session/" + code).json()
    assert session["game_started"] is True
    assert session["game_id"] == "test-game"
    assert session["minimum_players"] == 2
    assert client.post("/session/" + code + "/start", json=payload).status_code == 409


@pytest.fixture
def quiplash_session(client):
    created = client.post("/session").json()
    code = created["session_id"]
    for player_id in ["first", "second"]:
        client.post(f"/session/{code}/join", json={"player_id": player_id, "name": player_id})
    assert client.post(f"/session/{code}/start", json={
        "game_id": "quiplash", "minimum_players": 2, "maximum_players": 4,
    }).status_code == 200
    return code, {"X-Host-Token": created["host_token"]}


def receive_message(socket, message_type):
    async def receive():
        with anyio.fail_after(2):
            for _ in range(8):
                message = await socket._send_rx.receive()
                data = json.loads(message["text"])
                if data["type"] == message_type:
                    return data
        pytest.fail(f"Did not receive {message_type}")
    return socket.portal.call(receive)


@pytest.mark.parametrize("submit_answers", [True, False], ids=["answered", "skipped"])
def test_quiplash_completion_closes_answers(client, quiplash_session, submit_answers):
    code, headers = quiplash_session
    total_rounds = client.get(f"/session/{code}").json()["total_rounds"]
    assert client.post(f"/session/{code}/start-timer", headers=headers, json={
        "duration_seconds": 60,
    }).status_code == 200
    for round_number in range(1, total_rounds + 1):
        if submit_answers:
            for player_id in ["first", "second"]:
                assert client.post(f"/session/{code}/submit-answer", json={
                    "player_id": player_id, "answer": "A funny answer", "current_round": round_number,
                }).status_code == 200

        assert client.post(f"/session/{code}/advance-round", headers=headers).status_code == 200
        state = client.get(f"/session/{code}").json()
        assert (state["phase"] == "finished") is (round_number == total_rounds)
        if state["phase"] != "finished":
            assert state["current_round"] == round_number + 1
            assert all(group["answers"] == {} for group in state["groups"])

    assert state["game_id"] == "quiplash"
    assert state["current_round"] == total_rounds
    assert state["round_deadline"] is None
    answers = {player_id: answer for group in state["groups"] for player_id, answer in group["answers"].items()}
    assert answers == ({"first": "A funny answer", "second": "A funny answer"} if submit_answers else {})
    response = client.post(f"/session/{code}/submit-answer", json={
        "player_id": "first", "answer": "Too late", "current_round": total_rounds,
    })
    assert response.status_code == 400
    assert client.get(f"/session/{code}").json() == state


def test_quiplash_completion_updates_players_and_survives_reconnect(client, quiplash_session):
    code, headers = quiplash_session
    total_rounds = client.get(f"/session/{code}").json()["total_rounds"]
    with client.websocket_connect(f"/ws/session/{code}/player/first") as first:
        receive_message(first, "player_prompt")
        with client.websocket_connect(f"/ws/session/{code}/player/second") as second:
            receive_message(second, "player_prompt")
            for round_number in range(1, total_rounds + 1):
                assert client.post(f"/session/{code}/advance-round", headers=headers).status_code == 200
                message_type = "game_finished" if round_number == total_rounds else "round_updated"
                assert receive_message(first, message_type) == receive_message(second, message_type)
            assert client.get(f"/session/{code}").json()["phase"] == "finished"

    with client.websocket_connect(f"/ws/session/{code}/player/first") as socket:
        assert receive_message(socket, "game_finished")["session_id"] == code
        assert client.get(f"/session/{code}").json()["phase"] == "finished"


def test_voting_options_survive_reconnect(client, quiplash_session):
    code, _ = quiplash_session
    for player_id in ["first", "second"]:
        assert client.post(f"/session/{code}/submit-answer", json={
            "player_id": player_id, "answer": "A funny answer", "current_round": 1,
        }).status_code == 200
    with client.websocket_connect(f"/ws/session/{code}/player/first") as socket:
        assert receive_message(socket, "voting_started")["current_round"] == 1
