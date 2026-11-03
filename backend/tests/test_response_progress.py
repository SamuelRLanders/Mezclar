import asyncio

import pytest
from fastapi import HTTPException, WebSocketDisconnect

from backend.app.api.routes_player import submit_answer
from backend.app.models.schemas import SubmitAnswerRequest
from backend.app.sessions import registry


@pytest.fixture
def response_game(client):
    created = client.post("/session", json={"settings": {
        "rounds": 3, "options": {"allowLateJoin": True},
    }}).json()
    code = created["session_id"]
    for player_id in ["p1", "p2", "p3", "p4"]:
        client.post(f"/session/{code}/join", json={"player_id": player_id, "name": player_id})
    assert client.post(f"/session/{code}/start", json={
        "game_id": "quiplash", "minimum_players": 2, "maximum_players": 10,
    }).status_code == 200
    return code, created["host_token"]


def test_concurrent_submissions_count_each_player_once(client, response_game):
    code, _ = response_game
    session = registry.get_session(code)
    assert session.response_progress() == {
        "submitted_count": 0, "eligible_count": 4, "submitted_player_ids": [],
    }

    async def submit_all():
        return await asyncio.gather(*[
            submit_answer(code, SubmitAnswerRequest(player_id=player_id, answer=answer))
            for player_id, answer in [("p1", "first"), ("p1", "duplicate"), ("p2", "second")]
        ], return_exceptions=True)

    results = asyncio.run(submit_all())
    assert sum(isinstance(result, HTTPException) for result in results) == 1
    assert session.response_progress() == {
        "submitted_count": 2, "eligible_count": 4, "submitted_player_ids": ["p1", "p2"],
    }
    group = session.get_player_group_index(1, "p1")
    assert session.group_answers[1][group]["p1"] == "first"
    assert client.get(f"/session/{code}").json()["submitted_count"] == 2


def test_eligibility_and_counts_reset_for_the_next_round(client, response_game):
    code, token = response_game
    client.post(f"/session/{code}/submit-answer", json={"player_id": "p1", "answer": "hello"})
    client.post(f"/session/{code}/join", json={"player_id": "late", "name": "late"})
    assert client.get(f"/session/{code}").json()["eligible_count"] == 4
    client.post(f"/session/{code}/kick", json={"player_id": "p4"})
    assert client.get(f"/session/{code}").json()["eligible_count"] == 3
    assert client.post(f"/session/{code}/advance-round", headers={"X-Host-Token": token}).status_code == 200
    state = client.get(f"/session/{code}").json()
    assert state["current_round"] == 2
    assert state["submitted_count"] == 0
    assert state["eligible_count"] == 4
    assert state["submitted_player_ids"] == []


def test_host_receives_live_counts_without_duplicate_updates(client, response_game):
    code, token = response_game
    assert "host_token" not in client.get(f"/session/{code}").json()
    with client.websocket_connect(f"/ws/session/{code}/host?token={token}") as socket:
        for player_id in ["p1", "p1", "p2"]:
            response = client.post(f"/session/{code}/submit-answer", json={
                "player_id": player_id, "answer": "hello",
            })
            if response.status_code == 200:
                message = socket.receive_json()
                assert message["type"] == "response_count_updated"
                assert message["current_round"] == 1
                assert message["eligible_count"] == 4
                assert message["submitted_count"] == (1 if player_id == "p1" else 2)
            else:
                assert response.status_code == 400


@pytest.mark.parametrize("token", ["", "wrong", "another-session"])
def test_host_socket_requires_its_own_token(client, response_game, token):
    code, _ = response_game
    if token == "another-session":
        token = client.post("/session").json()["host_token"]
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(f"/ws/session/{code}/host?token={token}"):
            pass
    assert error.value.code == 1008
