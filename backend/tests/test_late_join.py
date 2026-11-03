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


# --- Quiplash late joining ---

import asyncio
from unittest.mock import AsyncMock, patch

from backend.app.api.voting import start_voting
from backend.app.sessions import registry
from backend.app.sessions.session import Session
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

def join_late(client, code, player_id="late"):
    return client.post("/session/" + code + "/join", json={"player_id": player_id, "name": player_id})

def groups_containing(session, round_number, player_id):
    return [group for group in session.round_groups[round_number] if player_id in group]

def test_late_joiner_waits_until_next_round(client):
    code = start_quiplash(client)
    response = join_late(client, code)
    assert response.status_code == 200
    assert response.json()["game_started"] is True

    session = registry.get_session(code)
    assert session.waiting_players == ["late"]
    assert groups_containing(session, 1, "late") == []
    assert "late" not in session.scores

def test_late_joiner_inserted_into_current_and_remaining_rounds(client):
    code = start_quiplash(client)
    join_late(client, code)
    assert client.post("/session/" + code + "/advance-round", headers={"X-Host-Token": registry.get_session(code).host_token}).status_code == 200

    session = registry.get_session(code)
    assert session.current_round == 2
    assert groups_containing(session, 1, "late") == []
    assert len(groups_containing(session, 2, "late")) == 1
    assert len(groups_containing(session, 3, "late")) == 1
    assert session.scores["late"] == 0
    assert session.waiting_players == []

def test_late_joiner_joins_smallest_group(client):
    code = start_quiplash(client)
    join_late(client, code)
    client.post("/session/" + code + "/advance-round", headers={"X-Host-Token": registry.get_session(code).host_token})

    # Four players form two pairs, so the late joiner makes one group of three.
    sizes = sorted(len(group) for group in registry.get_session(code).round_groups[2])
    assert sizes == [2, 3]

def test_round_joined_sent_only_to_inserted_player(client):
    code = start_quiplash(client)
    join_late(client, code)

    with patch(
        "backend.app.api.routes_host.connection_manager.send_to_player",
        new_callable=AsyncMock,
    ) as send_to_player:
        client.post("/session/" + code + "/advance-round", headers={"X-Host-Token": registry.get_session(code).host_token})

    # Some callers pass positional args and some pass keywords.
    sent = [
        (call.kwargs.get("player_id") or call.args[1], call.kwargs.get("message") or call.args[2])
        for call in send_to_player.await_args_list
    ]
    round_joined = [(player_id, message) for player_id, message in sent if message["type"] == "round_joined"]
    assert len(round_joined) == 1
    assert round_joined[0][0] == "late"
    assert round_joined[0][1]["current_round"] == 2

def test_late_join_rejected_in_last_round(client):
    code = start_quiplash(client, rounds=1)
    response = join_late(client, code)
    assert response.status_code == 403
    assert "last round" in response.json()["detail"]
    assert "late" not in registry.get_session(code).players

def test_late_join_rejected_after_advancing_to_last_round(client):
    code = start_quiplash(client, rounds=2)
    client.post("/session/" + code + "/advance-round", headers={"X-Host-Token": registry.get_session(code).host_token})
    response = join_late(client, code)
    assert response.status_code == 403
    assert "last round" in response.json()["detail"]

def test_existing_player_can_rejoin_in_last_round(client):
    code = start_quiplash(client, rounds=1)
    assert join_late(client, code, "p1").status_code == 200

def test_kicked_waiting_player_is_not_inserted(client):
    code = start_quiplash(client)
    join_late(client, code)
    client.post("/session/" + code + "/kick", json={"player_id": "late"})
    client.post("/session/" + code + "/advance-round", headers={"X-Host-Token": registry.get_session(code).host_token})

    session = registry.get_session(code)
    assert session.waiting_players == []
    assert all(groups_containing(session, r, "late") == [] for r in (1, 2, 3))

def test_session_response_includes_total_rounds(client):
    code = start_quiplash(client, rounds=2)
    assert client.get("/session/" + code).json()["total_rounds"] == 2

def test_voting_skips_waiting_players():
    session = Session("abc123", settings={"rounds": 3})
    session.configure_game("quiplash", 2, 50)
    for i in range(4):
        session.add_player(f"player{i}", f"Player {i}")
    session.start_game()
    session.add_late_player("late", "Late")

    with patch(
        "backend.app.api.voting.connection_manager.send_to_player",
        new_callable=AsyncMock,
    ) as send_to_player:
        asyncio.run(start_voting(session, 1))

    recipients = [call.args[1] for call in send_to_player.await_args_list]
    assert session.phase == "voting"
    assert "late" not in recipients
    assert len(recipients) == 4

def test_grouped_player_told_round_joined_on_reconnect(client):
    code = start_quiplash(client)
    join_late(client, code)
    client.post("/session/" + code + "/advance-round", headers={"X-Host-Token": registry.get_session(code).host_token})

    with client.websocket_connect("/ws/session/" + code + "/player/late") as socket:
        types = [socket.receive_json()["type"] for _ in range(4)]
    assert types == ["connected", "game_started", "round_joined", "player_prompt"]

def test_waiting_player_not_told_round_joined_on_connect(client):
    code = start_quiplash(client)
    join_late(client, code)

    with client.websocket_connect("/ws/session/" + code + "/player/late") as socket:
        assert socket.receive_json()["type"] == "connected"
        assert socket.receive_json()["type"] == "game_started"

    session = registry.get_session(code)
    assert not session.is_player_in_current_round("late")

def test_disconnect_ignores_replaced_socket():
    old_socket, new_socket = object(), object()
    connection_manager.active_connections["abc123"]["p1"] = new_socket

    # The old socket closing must not remove the newer one.
    connection_manager.disconnect("abc123", "p1", websocket=old_socket)
    assert connection_manager.active_connections["abc123"]["p1"] is new_socket

    connection_manager.disconnect("abc123", "p1", websocket=new_socket)
    assert "abc123" not in connection_manager.active_connections


# --- Auto-generated names are enforced on join ---

def test_late_joiner_gets_generated_name_when_auto_names_on(client):
    code = client.post("/session", json={"settings": {
        "options": {"allowLateJoin": True, "autoGenerateNames": True},
    }}).json()["session_id"]
    for player_id in ["p1", "p2"]:
        client.post("/session/" + code + "/join", json={"player_id": player_id})
    client.post("/session/" + code + "/start", json={
        "game_id": "quiplash", "minimum_players": 2, "maximum_players": 10,
    })

    with patch("backend.app.sessions.session.generate_unique_name", return_value="Generated Late"):
        response = join_late(client, code)
    assert response.status_code == 200
    assert response.json()["name"] == "Generated Late"

def test_lobby_joiner_gets_generated_name_when_auto_names_on(client):
    code = client.post("/session", json={"settings": {
        "options": {"autoGenerateNames": True},
    }}).json()["session_id"]

    with patch("backend.app.sessions.session.generate_unique_name", return_value="Generated Lobby"):
        response = client.post("/session/" + code + "/join", json={"player_id": "p1", "name": "Chosen"})
    assert response.json()["name"] == "Generated Lobby"

def test_chosen_name_used_when_auto_names_off(client):
    code = client.post("/session").json()["session_id"]
    response = client.post("/session/" + code + "/join", json={"player_id": "p1", "name": "Chosen"})
    assert response.json()["name"] == "Chosen"
