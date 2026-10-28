from backend.app.models.schemas import (
    HidePlayerRequest,
    KickPlayerRequest,
    ToggleAutoNamesRequest,
    CreateSessionRequest,
    SessionPlayerResponse,
    SessionResponse,
    StartGameRequest,
    ModPlayerRequest,
)
from fastapi import APIRouter, HTTPException
from backend.app.sessions.registry import get_or_create_session, get_session
from backend.app.sessions import registry
from backend.app.api import SessionCode

from backend.app.websockets.connection_manager import (
    connection_manager,
)
from backend.app.websockets.handlers import broadcast_roster

router = APIRouter()

@router.post("/session/{session_id}/toggle-auto-names")
def toggle_auto_names(session_id: str, request: ToggleAutoNamesRequest) -> None:
    session = get_or_create_session(session_id)
    session.set_auto_generate(request.enabled)

@router.post("/session/{session_id}/toggle-profanity-filter")
def toggle_profanity_filter(session_id: str, request: ToggleAutoNamesRequest) -> None:
    session = get_or_create_session(session_id)
    session.set_profanity_filter(request.enabled)

@router.post("/session", response_model=SessionResponse)
def create_session(request: CreateSessionRequest | None = None) -> SessionResponse:
    try:
        session = registry.create_session(request)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return get_session_info(session.session_id)

@router.get("/session/{session_id}", response_model=SessionResponse)
def get_session_info(session_id: SessionCode) -> SessionResponse:
    session = get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    players = [SessionPlayerResponse(player_id=player.player_id, name=player.name, ready=player.ready, hidden=player.hidden, is_mod=player.is_mod) for player in session.players.values()]

    return SessionResponse(
        session_id=session.session_id, player_count=len(players), players=players,
        game_started=session.game_started, host_name=session.host_name,
        settings=session.settings, auto_generate_names=session.auto_generate_names,
        allow_late_join=session.allow_late_join,
        game_id=session.game_id, minimum_players=session.minimum_players,
        maximum_players=session.maximum_players, current_round=session.current_round,
        current_prompt=session.current_prompt, answers=session.answers
    )

@router.post("/session/{session_id}/start")
async def start_game(session_id: str, request: StartGameRequest,) -> dict:
    session = get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    if session.game_started:
        raise HTTPException(
            status_code=409,
            detail="Game has already started.",
        )

    try:
        session.configure_game(
            game_id=request.game_id,
            minimum_players=request.minimum_players,
            maximum_players=request.maximum_players,
        )

        session.start_game()

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    await connection_manager.broadcast_to_session(
        session_id=session.session_id,
        message={
            "type": "game_started",
            "session_id": session.session_id,
            "game_id": session.game_id,
        },
    )

    return {
        "session_id": session.session_id,
        "game_id": session.game_id,
        "game_started": session.game_started,
        "player_count": len(session.players),
    }

@router.post("/session/{session_id}/kick")
async def kick_player(session_id: str, request: KickPlayerRequest) -> dict:
    session = get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    try:
        session.kick_player(request.player_id)
    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    await connection_manager.send_to_player(
        session_id, request.player_id,
        {"type": "kicked", "session_id": session_id},
    )
    await connection_manager.disconnect_player(session_id, request.player_id)
    await broadcast_roster(session)

    return { "session_id": session.session_id }

@router.post("/session/{session_id}/hide")
async def hide_player(session_id: str, request: HidePlayerRequest) -> SessionPlayerResponse:
    session = get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    try:
        player = session.hide_player(request.player_id, request.hidden)
    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    await broadcast_roster(session)

    return SessionPlayerResponse(player_id = player.player_id, name = player.name, ready = player.ready, hidden = player.hidden, is_mod = player.is_mod)

@router.post("/session/{session_id}/mod")
async def mod_player(session_id: str, request: ModPlayerRequest) -> SessionPlayerResponse:
    session = get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )
    player = session.mod_player(request.player_id, request.is_mod)

    await broadcast_roster(session)

    return SessionPlayerResponse(player_id = player.player_id, name = player.name, ready = player.ready, hidden = player.hidden, is_mod = player.is_mod)




@router.post("/session/{session_id}/advance-round")
async def advance_round(session_id: str) -> dict[str, str | int]:
    session = get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    try:
        session.advance_round()
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    await connection_manager.broadcast_to_session(
        session_id=session.session_id,
        message={
            "type": "round_updated",
            "session_id": session.session_id,
            "current_round": session.current_round,
            "current_prompt": session.current_prompt,
        },
    )

    return {
        "session_id": session.session_id,
        "current_round": session.current_round,
        "current_prompt": session.current_prompt or "",
    }