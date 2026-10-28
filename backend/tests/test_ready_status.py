import pytest

@pytest.fixture
def joined_lobby(client):
    code = client.post("/session").json()["session_id"]
    for player_id, name in [("first", "Casey"), ("second", "Taylor"), ("third", "Jordan")]:
        assert client.post("/session/" + code + "/join", json={"player_id": player_id, "name": name}).status_code == 200
    return code

def test_api_marks_existing_player_ready(client, joined_lobby):
    response = client.patch("/session/" + joined_lobby + "/players/first/ready", json={"ready": True})
    assert response.status_code == 200
    assert response.json() == {"player_id": "first", "name": "Casey", "ready": True, "hidden": False, "is_mod": False}

def test_api_marks_ready_player_not_ready(client, joined_lobby):
    url = "/session/" + joined_lobby + "/players/first/ready"
    client.patch(url, json={"ready": True})
    response = client.patch(url, json={"ready": False})
    assert response.status_code == 200
    assert response.json() == {"player_id": "first", "name": "Casey", "ready": False, "hidden": False, "is_mod": False}

def test_repeated_ready_requests_and_rejoining_do_not_reset_status(client, joined_lobby):
    url = "/session/" + joined_lobby + "/players/first/ready"
    for _ in range(2):
        assert client.patch(url, json={"ready": True}).json()["ready"] is True
    response = client.post("/session/" + joined_lobby + "/join", json={"player_id": "first", "name": "Changed"})
    assert response.json()["ready"] is True
    assert response.json()["name"] == "Casey"
    assert client.get("/session/" + joined_lobby).json()["player_count"] == 3

def test_ready_status_is_scoped_to_the_session(client, joined_lobby):
    other = client.post("/session").json()["session_id"]
    client.post("/session/" + other + "/join", json={"player_id": "first", "name": "Other Casey"})
    client.patch("/session/" + joined_lobby + "/players/first/ready", json={"ready": True})
    assert client.get("/session/" + other).json()["players"][0]["ready"] is False
    response = client.patch("/session/" + other + "/players/second/ready", json={"ready": True})
    assert response.status_code == 404
    assert client.get("/session/" + joined_lobby).json()["players"][1]["ready"] is False

@pytest.mark.parametrize("payload", [
    {}, {"ready": None}, {"ready": "true"}, {"ready": 1}, {"ready": []}, {"ready": True, "name": "Changed"},
])
def test_invalid_ready_payload_does_not_change_the_player(client, joined_lobby, payload):
    response = client.patch("/session/" + joined_lobby + "/players/first/ready", json=payload)
    assert response.status_code == 422
    assert client.get("/session/" + joined_lobby).json()["players"][0]["ready"] is False
