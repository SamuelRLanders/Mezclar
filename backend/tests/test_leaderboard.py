from backend.app.sessions import registry
from backend.app.sessions.session import Session


def session_with_players(*player_ids: str) -> Session:
    session = Session("abc123")
    for player_id in player_ids:
        session.add_player(player_id, player_id)
    return session

def ranking(session):
    return [(entry["player_id"], entry["score"], entry["rank"]) for entry in session.get_leaderboard()]

def start_quiplash(client):
    code = client.post("/session", json={"settings": {
        "options": {"allowLateJoin": True},
    }}).json()["session_id"]
    for player_id in ["p1", "p2", "p3", "p4"]:
        client.post("/session/" + code + "/join", json={"player_id": player_id, "name": player_id})
    client.post("/session/" + code + "/start", json={
        "game_id": "quiplash", "minimum_players": 2, "maximum_players": 10,
    })
    return code


def test_every_player_listed_with_zero_before_votes():
    session = session_with_players("a", "b", "c")
    assert ranking(session) == [("a", 0, 1), ("b", 0, 1), ("c", 0, 1)]

def test_sorted_by_score_highest_first():
    session = session_with_players("a", "b", "c")
    session.scores = {"a": 1, "b": 5, "c": 3}
    assert [player_id for player_id, _, _ in ranking(session)] == ["b", "c", "a"]

def test_ties_share_rank_and_keep_join_order():
    session = session_with_players("a", "b", "c", "d")
    session.scores = {"a": 2, "b": 5, "c": 2, "d": 1}
    assert ranking(session) == [("b", 5, 1), ("a", 2, 2), ("c", 2, 2), ("d", 1, 4)]

def test_late_joiner_listed_last_and_waiting(client):
    code = start_quiplash(client)
    client.post("/session/" + code + "/join", json={"player_id": "late", "name": "late"})

    leaderboard = registry.get_session(code).get_leaderboard()
    assert leaderboard[-1]["player_id"] == "late"
    assert leaderboard[-1]["score"] == 0
    assert leaderboard[-1]["waiting"] is True
    assert all(entry["waiting"] is False for entry in leaderboard[:-1])

def test_late_joiner_stops_waiting_once_in_a_round(client):
    code = start_quiplash(client)
    client.post("/session/" + code + "/join", json={"player_id": "late", "name": "late"})
    client.post("/session/" + code + "/advance-round", headers={"X-Host-Token": registry.get_session(code).host_token})

    entry = registry.get_session(code).get_leaderboard()[-1]
    assert entry["player_id"] == "late"
    assert entry["waiting"] is False

def test_kicked_player_removed():
    session = session_with_players("a", "b")
    session.scores = {"a": 3, "b": 1}
    session.kick_player("a")
    assert ranking(session) == [("b", 1, 1)]

def test_hidden_flag_passed_through():
    session = session_with_players("a", "b")
    session.hide_player("a")

    hidden = {entry["player_id"]: entry["hidden"] for entry in session.get_leaderboard()}
    assert hidden == {"a": True, "b": False}

def test_session_response_includes_leaderboard(client):
    code = client.post("/session").json()["session_id"]
    client.post("/session/" + code + "/join", json={"player_id": "p1", "name": "Casey"})

    entry = client.get("/session/" + code).json()["leaderboard"][0]
    assert entry == {
        "player_id": "p1", "name": "Casey", "hidden": False,
        "score": 0, "rank": 1, "waiting": False,
    }
