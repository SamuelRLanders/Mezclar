import asyncio

from fastapi import WebSocket, WebSocketDisconnect

from backend.app.sessions.session import Session
from backend.app.api.voting import send_voting_options
from backend.app.websockets.connection_manager import (
    connection_manager,
)

# Page changes briefly close a player's socket; only log disconnects that last.
DISCONNECT_GRACE_SECONDS = 5

# Keep references so pending tasks aren't garbage-collected before they run.
_background_tasks: set[asyncio.Task] = set()


async def log_disconnect_after_grace(session: Session, player_id: str) -> None:
    await asyncio.sleep(DISCONNECT_GRACE_SECONDS)

    player = session.get_player(player_id)
    if (
        player is None
        or player_id in session.disconnected_players
        or connection_manager.is_connected(session.session_id, player_id)
    ):
        return

    session.disconnected_players.add(player_id)
    session.log_event("player_disconnected", "disconnected", player)


def public_players(session: Session) -> list[dict]:
    return [
        {
            "player_id": player.player_id,
            "name": "Hidden player" if player.hidden else player.name,
            "is_mod": player.is_mod,
        }
        for player in session.players.values()
    ]


async def broadcast_roster(
    session: Session,
    exclude: str | None = None,
) -> None:
    await connection_manager.broadcast_to_session(
        session_id=session.session_id,
        message={
            "type": "players_updated",
            "players": public_players(session),

        },
        exclude=exclude,
    )


async def handle_join(
    websocket: WebSocket,
    session: Session,
    player_id: str,
    requested_name: str | None,
) -> None:
    player = session.get_player(player_id)

    if player is None:
        await websocket.close(code=1008)
        return

    await connection_manager.connect(
        session_id=session.session_id,
        player_id=player_id,
        websocket=websocket,
    )

    if player_id in session.disconnected_players:
        session.disconnected_players.discard(player_id)
        session.log_event("player_reconnected", "reconnected", player)

    await websocket.send_json(
        {
            "type": "connected",
            "session_id": session.session_id,
            "player_id": player.player_id,
            "name": player.name,
            "ready": player.ready,
            "game_id": session.settings.get("gameId"),
            "players": public_players(session),
        }
    )

    await broadcast_roster(session, exclude=player_id)

    if session.game_started:
        await websocket.send_json({
            "type": "game_started",
            "session_id": session.session_id,
            "game_id": session.game_id,
        })

        if session.phase == "finished":
            await websocket.send_json({"type": "game_finished", "session_id": session.session_id})

        # Restore the player's Keywords screen after a refresh or reconnect.
        if session.game_id == "keywords":
            await send_keywords_state(session, player_id)

        if session.is_player_in_current_round(player_id):
            await websocket.send_json({
                "type": "round_joined",
                "session_id": session.session_id,
                "current_round": session.current_round,
            })

    await send_player_prompt(session, player_id)
    if session.phase == "voting":
        await send_voting_options(session, session.current_round, [player_id])

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        removed = connection_manager.disconnect(
            session_id=session.session_id,
            player_id=player_id,
            websocket=websocket,
        )
        if removed:
            task = asyncio.create_task(log_disconnect_after_grace(session, player_id))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)


async def send_player_prompt(
    session: Session,
    player_id: str,
    round_number: int | None = None,
) -> None:
    """Send the prompt assigned to this player's group."""
    if not session.game_started or session.game_id != "quiplash" or session.phase == "finished":
        return

    if round_number is None:
        round_number = session.current_round

    try:
        group_index = session.get_player_group_index(
            round_number,
            player_id,
        )
    except ValueError:
        return

    prompt = session.group_prompts.get(
        round_number,
        {},
    ).get(group_index)

    if prompt is None:
        return

    await connection_manager.send_to_player(
        session_id=session.session_id,
        player_id=player_id,
        message={
            "type": "player_prompt",
            "session_id": session.session_id,
            "current_round": round_number,
            "current_prompt": prompt,
        },
    )


async def send_keywords_state(session: Session, player_id: str) -> None:
    # Send one player their private Keywords view (used after actions and on reconnect).
    if session.keywords is None:
        return
    try:
        view = session.keywords.player_view(player_id)
    except ValueError:
        # Players who aren't in a group (e.g. joined late) have nothing to show.
        return
    await connection_manager.send_to_player(
        session.session_id, player_id, {"type": "keywords_state", **view},
    )
