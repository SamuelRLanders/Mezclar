import asyncio
from unittest.mock import AsyncMock, patch

from backend.app.api.voting import start_voting
from backend.app.sessions import registry
from backend.app.sessions.session import MAX_EVENT_LOG, Session
from backend.app.websockets import handlers
from backend.app.websockets.connection_manager import connection_manager


def start_quiplash(client, rounds=3):
    code = client.post("/session", json={"settings": {
        "rounds": rounds, "options": {"allowLateJoin": True},
    }}).json()["session_id"]
    for player_id in ["p1", "p2", "p3", "p4"]:
        client.post("/session/" + code + "/join", json={"player_id": player_id, "name": player_id})
    client.post("/session/" + code + "/start", json={
        "game_id": "quiplash", "minimum_players": 2, "maximum_players": 10,
    })
    return code

def event_types(session):
    return [event["type"] for event in session.event_log]

def started_session() -> Session:
    session = Session("abc123", settings={"rounds": 3})
    session.configure_game("quiplash", 2, 50)
    for i in range(4):
        session.add_player(f"player{i}", f"Player {i}")
    session.start_game()
    return session

def run_grace(session, player_id):
    with patch.object(handlers, "DISCONNECT_GRACE_SECONDS", 0):
        asyncio.run(handlers.log_disconnect_after_grace(session, player_id))


def test_log_event_assigns_ids_and_keeps_newest():
    session = Session("abc123")
    for i in range(MAX_EVENT_LOG + 5):
        session.log_event("test", f"event {i}")

    assert len(session.event_log) == MAX_EVENT_LOG
    assert session.event_log[0]["id"] == 6
    assert session.event_log[-1]["message"] == f"event {MAX_EVENT_LOG + 4}"

def test_log_event_records_player():
    session = Session("abc123")
    player = session.add_player("p1", "Casey")
    session.log_event("player_joined", "joined the lobby", player)

    event = session.event_log[-1]
    assert event["player_id"] == "p1"
    assert event["player_name"] == "Casey"

def test_lobby_join_logged(client):
    code = client.post("/session").json()["session_id"]
    client.post("/session/" + code + "/join", json={"player_id": "p1", "name": "p1"})
    assert event_types(registry.get_session(code)) == ["player_joined"]

def test_rejoin_not_logged_again(client):
    code = client.post("/session").json()["session_id"]
    client.post("/session/" + code + "/join", json={"player_id": "p1", "name": "p1"})
    client.post("/session/" + code + "/join", json={"player_id": "p1", "name": "p1"})
    assert event_types(registry.get_session(code)) == ["player_joined"]

def test_late_join_logged(client):
    code = start_quiplash(client)
    client.post("/session/" + code + "/join", json={"player_id": "late", "name": "late"})

    event = registry.get_session(code).event_log[-1]
    assert event["type"] == "player_joined_late"
    assert event["player_id"] == "late"
    assert "waiting for the next round" in event["message"]

def test_round_start_then_insert_logged(client):
    code = start_quiplash(client)
    client.post("/session/" + code + "/join", json={"player_id": "late", "name": "late"})
    client.post("/session/" + code + "/advance-round", headers={"X-Host-Token": registry.get_session(code).host_token})

    session = registry.get_session(code)
    assert event_types(session)[-2:] == ["round_started", "player_inserted"]
    assert session.event_log[-1]["message"] == "jumped in at round 2"

def test_game_lifecycle_logged_once(client):
    code = start_quiplash(client, rounds=1)
    client.post("/session/" + code + "/advance-round", headers={"X-Host-Token": registry.get_session(code).host_token})
    client.post("/session/" + code + "/advance-round", headers={"X-Host-Token": registry.get_session(code).host_token})

    types = event_types(registry.get_session(code))
    assert types.count("game_started") == 1
    assert types.count("game_finished") == 1

def test_kick_logged_without_disconnect(client):
    code = start_quiplash(client)
    client.post("/session/" + code + "/kick", json={"player_id": "p1"})

    session = registry.get_session(code)
    assert event_types(session)[-1] == "player_kicked"
    assert session.event_log[-1]["player_name"] == "p1"
    assert "player_disconnected" not in event_types(session)

def test_voting_start_logged():
    session = started_session()
    with patch(
        "backend.app.api.voting.connection_manager.send_to_player",
        new_callable=AsyncMock,
    ):
        asyncio.run(start_voting(session, 1))

    assert session.event_log[-1]["type"] == "voting_started"
    assert session.event_log[-1]["message"] == "Voting opened for round 1."

def test_disconnect_logged_when_player_stays_gone():
    session = started_session()
    run_grace(session, "player0")

    assert session.event_log[-1]["type"] == "player_disconnected"
    assert "player0" in session.disconnected_players

def test_disconnect_not_logged_when_player_came_back():
    session = started_session()
    connection_manager.active_connections[session.session_id]["player0"] = object()
    run_grace(session, "player0")

    assert "player_disconnected" not in event_types(session)

def test_disconnect_not_logged_twice():
    session = started_session()
    run_grace(session, "player0")
    run_grace(session, "player0")

    assert event_types(session).count("player_disconnected") == 1

def test_disconnect_not_logged_for_removed_player():
    session = started_session()
    session.remove_player("player0")
    run_grace(session, "player0")

    assert "player_disconnected" not in event_types(session)

def test_reconnect_logged_after_logged_disconnect(client):
    code = start_quiplash(client)
    session = registry.get_session(code)
    session.disconnected_players.add("p1")

    with client.websocket_connect("/ws/session/" + code + "/player/p1") as socket:
        socket.receive_json()

    assert "player_reconnected" in event_types(session)
    assert "p1" not in session.disconnected_players

def test_first_connect_not_logged_as_reconnect(client):
    code = start_quiplash(client)
    with client.websocket_connect("/ws/session/" + code + "/player/p1") as socket:
        socket.receive_json()

    assert "player_reconnected" not in event_types(registry.get_session(code))

def test_kick_clears_disconnected_state():
    session = started_session()
    session.disconnected_players.add("player0")
    session.kick_player("player0")
    assert "player0" not in session.disconnected_players

def test_session_response_includes_event_log(client):
    code = client.post("/session").json()["session_id"]
    client.post("/session/" + code + "/join", json={"player_id": "p1", "name": "Casey"})

    event = client.get("/session/" + code).json()["event_log"][0]
    assert set(event) == {"id", "timestamp", "type", "player_id", "player_name", "message"}
    assert event["player_name"] == "Casey"
    assert event["message"] == "joined the lobby"
