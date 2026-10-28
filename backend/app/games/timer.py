import asyncio

from backend.app.sessions import registry
from backend.app.sessions.session import Session
from backend.app.websockets.connection_manager import connection_manager


async def broadcast_round(session: Session) -> None:
    await connection_manager.broadcast_to_session(session.session_id, {
        "type": "round_updated",
        "session_id": session.session_id,
        "current_round": session.current_round,
        "current_prompt": session.current_prompt,
        "game_completed": session.game_completed,
        "game_paused": session.game_paused,
        "remaining_seconds": session.remaining_seconds,
    })


async def run_round_timers() -> None:
    while True:
        for session in list(registry._sessions.values()):
            if session.round_deadline is not None and session.remaining_seconds <= 0:
                session.advance_round()
                await broadcast_round(session)
        await asyncio.sleep(0.1)
