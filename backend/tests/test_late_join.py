def start_game(client, options):
    code = client.post("/session", json={"settings": {"options": options}}).json()["session_id"]
    for player_id in ["first", "second"]:
        client.post("/session/" + code + "/join", json={"player_id": player_id, "name": player_id})
    client.post("/session/" + code + "/start", json={
        "game_id": "test-game", "minimum_players": 2, "maximum_players": 4,
    })
    return code

def test_late_join_disabled_by_default(client):
    code = client.post("/session").json()["session_id"]
    assert client.get("/session/" + code).json()["allow_late_join"] is False

def test_new_player_rejected_mid_game_when_late_join_disabled(client):
    code = start_game(client, {"allowLateJoin": False})
    response = client.post("/session/" + code + "/join", json={"player_id": "late", "name": "late"})
    assert response.status_code == 403
    assert "late" not in [p["player_id"] for p in client.get("/session/" + code).json()["players"]]

def test_new_player_allowed_mid_game_when_late_join_enabled(client):
    code = start_game(client, {"allowLateJoin": True})
    response = client.post("/session/" + code + "/join", json={"player_id": "late", "name": "late"})
    assert response.status_code == 200

def test_existing_player_can_rejoin_when_late_join_disabled(client):
    code = start_game(client, {"allowLateJoin": False})
    response = client.post("/session/" + code + "/join", json={"player_id": "first", "name": "first"})
    assert response.status_code == 200
    assert response.json()["name"] == "first"

def test_join_response_reports_game_started(client):
    code = client.post("/session", json={"settings": {"options": {"allowLateJoin": True}}}).json()["session_id"]
    early = client.post("/session/" + code + "/join", json={"player_id": "early", "name": "early"})
    assert early.json()["game_started"] is False

    client.post("/session/" + code + "/join", json={"player_id": "second", "name": "second"})
    client.post("/session/" + code + "/start", json={
        "game_id": "test-game", "minimum_players": 2, "maximum_players": 4,
    })
    late = client.post("/session/" + code + "/join", json={"player_id": "late", "name": "late"})
    assert late.json()["game_started"] is True
