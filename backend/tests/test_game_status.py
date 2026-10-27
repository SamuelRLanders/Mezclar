import pytest

from backend.app.games.quiplash.prompts import QUIPLASH_PROMPTS


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
    code = client.post("/session").json()["session_id"]
    for player_id in ["first", "second"]:
        client.post(f"/session/{code}/join", json={"player_id": player_id, "name": player_id})
    assert client.post(f"/session/{code}/start", json={
        "game_id": "quiplash", "minimum_players": 2, "maximum_players": 4,
    }).status_code == 200
    return code


@pytest.mark.parametrize("submit_answers", [True, False], ids=["answered", "skipped"])
def test_quiplash_completion_closes_answers(client, quiplash_session, submit_answers):
    code = quiplash_session
    for round_number in range(1, len(QUIPLASH_PROMPTS) + 1):
        if submit_answers:
            for player_id in ["first", "second"]:
                assert client.post(f"/session/{code}/submit-answer", json={
                    "player_id": player_id, "answer": "A funny answer",
                }).status_code == 200

        assert client.post(f"/session/{code}/advance-round").status_code == 200
        state = client.get(f"/session/{code}").json()
        assert state["game_completed"] is (round_number == len(QUIPLASH_PROMPTS))
        if not state["game_completed"]:
            assert state["current_round"] == round_number + 1
            assert state["current_prompt"] == QUIPLASH_PROMPTS[round_number]
            assert state["answers"] == {}

    assert state["game_id"] == "quiplash"
    assert state["current_round"] == len(QUIPLASH_PROMPTS)
    assert state["current_prompt"] == QUIPLASH_PROMPTS[-1]
    assert state["answers"] == ({"first": "A funny answer", "second": "A funny answer"} if submit_answers else {})
    response = client.post(f"/session/{code}/submit-answer", json={
        "player_id": "first", "answer": "Too late",
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "The game has finished."
    assert client.post(f"/session/{code}/advance-round").status_code == 400
    assert client.get(f"/session/{code}").json() == state


def test_quiplash_completion_updates_players_and_survives_reconnect(client, quiplash_session):
    code = quiplash_session
    with client.websocket_connect(f"/ws/session/{code}/player/first") as first:
        assert first.receive_json()["type"] == "connected"
        assert first.receive_json()["type"] == "game_started"
        with client.websocket_connect(f"/ws/session/{code}/player/second") as second:
            assert second.receive_json()["type"] == "connected"
            assert second.receive_json()["type"] == "game_started"
            assert first.receive_json()["type"] == "players_updated"
            for _ in QUIPLASH_PROMPTS:
                assert client.post(f"/session/{code}/advance-round").status_code == 200
                message = first.receive_json()
                assert message == second.receive_json()
                assert message["type"] == "round_updated"
            assert client.get(f"/session/{code}").json()["game_completed"] is True

    with client.websocket_connect(f"/ws/session/{code}/player/first") as socket:
        assert socket.receive_json()["type"] == "connected"
        assert socket.receive_json()["type"] == "game_started"
        assert client.get(f"/session/{code}").json()["game_completed"] is True
