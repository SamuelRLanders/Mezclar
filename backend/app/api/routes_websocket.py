from hmac import compare_digest

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.sessions.registry import get_session
from backend.app.websockets.handlers import handle_join
from backend.app.websockets.connection_manager import connection_manager


router = APIRouter()


@router.websocket("/ws/session/{session_id}/host")
async def host_websocket(websocket: WebSocket, session_id: str, token: str = "") -> None:
    session = get_session(session_id)
    if session is None or not compare_digest(session.host_token.encode(), token.encode()):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    connections = connection_manager.host_connections[session_id]
    connections.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connections.discard(websocket)
        if not connections:
            connection_manager.host_connections.pop(session_id, None)


@router.websocket("/ws/session/{session_id}/player/{player_id}")
async def player_websocket(
    websocket: WebSocket,
    session_id: str,
    player_id: str,
) -> None:
    session = get_session(session_id)

    if session is None:
        await websocket.close(code=1008)
        return

    await handle_join(
        websocket=websocket,
        session=session,
        player_id=player_id,
        requested_name=None,
    )
