from fastapi import WebSocket, WebSocketDisconnect

from backend.app.sessions.session import Session
from backend.app.websockets.connection_manager import (
    connection_manager,
)


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

    await send_player_prompt(session, player_id)

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        connection_manager.disconnect(
            session_id=session.session_id,
            player_id=player_id,
        )


async def send_player_prompt(
    session: Session,
    player_id: str,
    round_number: int | None = None,
) -> None:
    """Send the prompt assigned to this player's group."""
    if not session.game_started or session.game_id != "quiplash":
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
