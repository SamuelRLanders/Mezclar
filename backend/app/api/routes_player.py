from httpx import request

from backend.app.models.schemas import (
    GenerateNameResponse, 
    RegenerateNameRequest,
    JoinSessionRequest,
    JoinSessionResponse,
    SubmitNameRequest,
    UpdateReadyStatusRequest,
    SessionPlayerResponse,
    SubmitAnswerRequest
)

from fastapi import APIRouter, HTTPException
from backend.app.sessions.registry import get_or_create_session, get_session
from backend.app.naming.generator import generate_unique_name, validate_name

router = APIRouter()

@router.post("/session/{session_id}/regenerate-name")
def regenerate_name(session_id: str, request: RegenerateNameRequest) -> GenerateNameResponse:
    session = get_or_create_session(session_id)
    try:
        name = session.regenerate_name(request.player_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return GenerateNameResponse(name=name)

@router.post("/session/{session_id}/submit-name")
def submit_name(session_id: str, request: SubmitNameRequest) -> GenerateNameResponse:
    session = get_or_create_session(session_id)
    try:
        name = session.submit_name(request.player_id, request.requested_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return GenerateNameResponse(name=name)

@router.post("/session/{session_id}/join", response_model=JoinSessionResponse)
def join_session(
    session_id: str,
    request: JoinSessionRequest
) -> JoinSessionResponse:
    session = get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )
    if session.use_profanity_filter:
        valid = validate_name(request.name)
        if not valid:
            raise HTTPException(
                status_code=400,
                detail="Name contains inappropriate content.",
            )
        
    if request.player_id in session.players:
        player = session.get_player(request.player_id)

    
        return JoinSessionResponse(
            player_id=player.player_id,
            name=player.name,
            session_id=session_id, 
            ready=player.ready,
            hidden=player.hidden,
            game_started=session.game_started,
        )

    if session.game_started and not session.allow_late_join:
        raise HTTPException(
            status_code=403,
            detail="This game is already in progress and isn't accepting new players.",
        )

    try:
        player = session.add_player(
            player_id=request.player_id,
            requested_name=request.name,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    return JoinSessionResponse(player_id=player.player_id, name=player.name, session_id=session_id, ready=player.ready, hidden=player.hidden, game_started=session.game_started)

@router.patch("/session/{session_id}/players/{player_id}/ready", response_model=SessionPlayerResponse)
def update_ready_status(session_id: str, player_id: str, request: UpdateReadyStatusRequest) -> SessionPlayerResponse:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        player = session.set_player_ready(player_id, request.ready)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return SessionPlayerResponse(player_id=player.player_id, name=player.name, ready=player.ready, hidden=player.hidden, is_mod=player.is_mod)

@router.post("/session/{session_id}/submit-answer")
def submit_answer(
    session_id: str,
    request: SubmitAnswerRequest,
) -> dict[str, str]:
    session = get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    try:
        session.submit_answer(request.player_id, request.answer)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    return {"message": "Answer submitted successfully."}
