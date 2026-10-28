from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from backend.app.models.schemas import CreateSessionRequest

from backend.app.sessions import registry

def test_create_session(client):
    response = client.post("/session", json={"host_name": "  George  ", "settings": {"rounds": 3}})
    assert response.status_code == 200
    session = response.json()
    assert len(session["session_id"]) == 4
    assert session["host_name"] == "George"
    assert session["settings"] == {"rounds": 3}
    assert session["players"] == []
    assert session["player_count"] == 0
    assert session["game_started"] is False
    assert client.get("/session/" + session["session_id"]).json() == session

def test_feature_branch_create_call_without_body_is_supported(client):
    response = client.post("/session")
    assert response.status_code == 200
    assert response.json()["host_name"] == "Host"

@pytest.mark.parametrize("payload", [
    {"host_name": ""}, {"host_name": "   "}, {"host_name": None}, {"host_name": 123},
    {"host_name": "George", "settings": []}, {"host_name": "George", "settings": None},
    {"host_name": "George", "session_id": "AB12"}, {"host_name": "George", "game_started": True},
    "not an object",
])
def test_invalid_create_request(client, payload):
    assert client.post("/session", json=payload).status_code == 422
    assert registry._sessions == {}

def test_unknown_session(client):
    response = client.get("/session/AB12")
    assert response.status_code == 404
    assert response.json() == {"detail": "Session not found"}
    assert registry._sessions == {}

def test_collision_retries_without_overwriting(client):
    with patch.object(registry, "generate_session_code", side_effect=["AB12", "AB12", "CD34"]):
        first = client.post("/session", json={"host_name": "George"})
        second = client.post("/session", json={"host_name": "Taylor"})
    assert first.status_code == second.status_code == 200
    assert first.json()["session_id"] == "AB12"
    assert second.json()["session_id"] == "CD34"
    assert registry.get_session("AB12").host_name == "George"

def test_sessions_do_not_share_mutable_data():
    request = CreateSessionRequest(host_name="George", settings={"round": {"duration": 30}})
    first, second = registry.create_session(request), registry.create_session(request)
    first.settings["round"]["duration"] = 60
    first.add_player("player1", "Taylor")
    assert second.settings == request.settings == {"round": {"duration": 30}}
    assert second.players == {}

def test_concurrent_creation_keeps_all_sessions():
    with ThreadPoolExecutor(max_workers=8) as executor:
        sessions = list(executor.map(registry.create_session, [CreateSessionRequest()] * 20))
    assert len({session.session_id for session in sessions}) == 20
    assert len(registry._sessions) == 20

def test_join_session_records_player_in_right_lobby(client):
    first, second = [client.post("/session").json()["session_id"] for _ in range(2)]
    response = client.post("/session/" + first + "/join", json={"player_id": "player1", "name": "  Casey  "})
    assert response.status_code == 200
    player = {"player_id": "player1", "name": "Casey", "ready": False, "hidden": False}
    assert response.json() == {**player, "session_id": first, "game_started": False}
    assert client.get("/session/" + first).json()["players"] == [player]
    assert client.get("/session/" + second).json()["players"] == []

@pytest.mark.parametrize("payload", [
    {}, {"player_id": ""}, {"player_id": "player1", "name": ""}, {"player_id": "player1", "name": "   "},
])
def test_join_requires_valid_player_data(client, payload):
    code = client.post("/session").json()["session_id"]
    assert client.post("/session/" + code + "/join", json=payload).status_code == 422
    assert client.get("/session/" + code).json()["players"] == []

def test_auto_names_use_the_created_lobby_settings(client):
    code = client.post("/session", json={"settings": {"options": {"autoGenerateNames": True}}}).json()["session_id"]
    with patch("backend.app.sessions.session.generate_unique_name", return_value="Generated Player"):
        response = client.post("/session/" + code + "/join", json={"player_id": "player1"})
    assert response.status_code == 200
    assert response.json()["name"] == "Generated Player"
    assert client.get("/session/" + code).json()["players"][0]["name"] == "Generated Player"

def test_name_toggle_and_regeneration_share_the_lobby_registry(client):
    code = client.post("/session").json()["session_id"]
    assert client.post("/session/" + code + "/toggle-auto-names", json={"enabled": True}).status_code == 200
    with patch("backend.app.sessions.session.generate_unique_name", side_effect=["First Name", "Next Name"]):
        client.post("/session/" + code + "/join", json={"player_id": "player1"})
        response = client.post("/session/" + code + "/regenerate-name", json={"player_id": "player1"})
    assert response.status_code == 200
    assert response.json() == {"name": "Next Name"}
    assert client.get("/session/" + code).json()["players"][0]["name"] == "Next Name"
