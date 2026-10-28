from backend.app.models.schemas import (
    HidePlayerRequest,
    KickPlayerRequest,
    ToggleAutoNamesRequest,
    CreateSessionRequest,
    SessionPlayerResponse,
    SessionResponse,
    StartGameRequest,
    ModPlayerRequest,
    StartRoundTimerRequest,
)
from fastapi import APIRouter, HTTPException
from backend.app.sessions.registry import get_or_create_session, get_session
from backend.app.sessions import registry
from backend.app.api import SessionCode
import asyncio
from datetime import datetime, timedelta, timezone

from backend.app.api.voting import start_voting

from backend.app.websockets.connection_manager import (
    connection_manager,
)
from backend.app.websockets.handlers import broadcast_roster, send_player_prompt

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

    groups = []

    if session.game_id == "quiplash" and session.game_started:
        round_groups = session.round_groups.get(
            session.current_round,
            [],
        )
        round_prompts = session.group_prompts.get(
            session.current_round,
            {},
        )
        round_answers = session.group_answers.get(
            session.current_round,
            {},
        )

        
        for group_index, player_ids in enumerate(round_groups):
            group_players = [
                player
                for player in players
                if player.player_id in player_ids
            ]

            group_answers = round_answers.get(group_index, {})

            # Get votes cast in this round and group.
            group_votes = (
                session.group_votes
                .get(session.current_round, {})
                .get(group_index, {})
            )

            # Count votes received by each player's answer.
            vote_counts = {
                player_id: sum(
                    1
                    for answer_owner_id in group_votes.values()
                    if answer_owner_id == player_id
                )
                for player_id in group_answers
            }

            groups.append({
                "group_index": group_index,
                "prompt": round_prompts.get(group_index, ""),
                "players": group_players,
                "answers": group_answers,
                "vote_counts": vote_counts,
            })


    return SessionResponse(
        session_id=session.session_id, player_count=len(players), players=players,
        game_started=session.game_started, host_name=session.host_name,
        settings=session.settings, auto_generate_names=session.auto_generate_names,
        allow_late_join=session.allow_late_join,
        game_id=session.game_id, minimum_players=session.minimum_players,
        maximum_players=session.maximum_players, current_round=session.current_round,
        current_prompt=session.current_prompt, answers=session.answers,
        round_duration_seconds=session.round_duration_seconds, round_deadline=session.round_deadline,
        groups=groups, phase=session.phase
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

        for player_id in session.players:
            await send_player_prompt(session, player_id)

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

    # Remember whether the current round has an active timer.
    timer_was_active = (
        session.round_deadline is not None
        and session.round_duration_seconds is not None
    )

    # Advance first. If this fails (for example, on the final round),
    # leave the existing timer untouched.
    try:
        session.advance_round()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    # Cancel the old timer after successfully advancing.
    if session.round_timer_task is not None:
        session.round_timer_task.cancel()
        session.round_timer_task = None

    session.round_deadline = None

    # If the host was using a timer, start a fresh one for the new round.
    if timer_was_active:
        deadline = datetime.now(timezone.utc) + timedelta(
            seconds=session.round_duration_seconds
        )
        session.round_deadline = deadline
        session.round_timer_task = asyncio.create_task(
            run_round_timer(session, session.current_round, deadline)
        )

    await connection_manager.broadcast_to_session(
        session.session_id,
        {
            "type": "round_updated",
            "session_id": session.session_id,
            "current_round": session.current_round,
            "current_prompt": session.current_prompt,
            "round_duration_seconds": session.round_duration_seconds,
            "round_deadline": (
                session.round_deadline.isoformat()
                if session.round_deadline is not None
                else None
            ),
        },
    )

    for player_id in session.players:
        await send_player_prompt(session, player_id)

    return {
        "session_id": session.session_id,
        "current_round": session.current_round,
        "current_prompt": session.current_prompt or "",
    }

async def run_round_timer(session, round_number: int, deadline: datetime) -> None:
    try:
        remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
        await asyncio.sleep(max(0, remaining))

        # Ignore this task if the round or timer has since changed.
        if (
            not session.game_started
            or session.current_round != round_number
            or session.round_deadline != deadline
        ):
            return

        # Fill in missing answers in each player's assigned group.
        groups = session.round_groups.get(round_number, [])
        round_answers = session.group_answers.setdefault(round_number, {})

        for group_index, group in enumerate(groups):
            group_answers = round_answers.setdefault(group_index, {})
            for player_id in group:
                if player_id not in group_answers:
                    group_answers[player_id] = "No answer submitted (time expired)"

        session.round_deadline = None
        session.round_timer_task = None

        await start_voting(session, round_number)

        # if session.current_round >= session.total_rounds:
        #     await connection_manager.broadcast_to_session(
        #         session.session_id,
        #         {
        #             "type": "round_timer_expired",
        #             "session_id": session.session_id,
        #             "current_round": session.current_round,
        #             "answers": session.answers,
        #         },
        #     )
        #     return

        # session.advance_round()

        # # Automatically time the next round using the same duration.
        # next_deadline = datetime.now(timezone.utc) + timedelta(
        #     seconds=session.round_duration_seconds
        # )
        # session.round_deadline = next_deadline
        # session.round_timer_task = asyncio.create_task(
        #     run_round_timer(session, session.current_round, next_deadline)
        # )

        # await connection_manager.broadcast_to_session(
        #     session.session_id,
        #     {
        #         "type": "round_updated",
        #         "session_id": session.session_id,
        #         "current_round": session.current_round,
        #         "current_prompt": session.current_prompt,
        #         "round_duration_seconds": session.round_duration_seconds,
        #         "round_deadline": next_deadline.isoformat(),
        #     },
        # )

        # for player_id in session.players:
        #     await send_player_prompt(session, player_id)

    except asyncio.CancelledError:
        # A host action can cancel this timer when changing rounds.
        raise

@router.post("/session/{session_id}/start-timer")
async def start_round_timer(
    session_id: str,
    request: StartRoundTimerRequest,
) -> dict[str, str]:
    session = get_session(session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.game_started:
        raise HTTPException(status_code=400, detail="The game has not started.")

    if session.game_id != "quiplash":
        raise HTTPException(status_code=400, detail="This game does not support round timers.")

    if not 10 <= request.duration_seconds <= 300:
        raise HTTPException(
            status_code=400,
            detail="Timer duration must be between 10 and 300 seconds.",
        )

    # Cancel any existing timer for this session.
    if session.round_timer_task is not None:
        session.round_timer_task.cancel()

    session.round_duration_seconds = request.duration_seconds
    deadline = datetime.now(timezone.utc) + timedelta(
        seconds=request.duration_seconds
    )
    session.round_deadline = deadline
    session.round_timer_task = asyncio.create_task(
        run_round_timer(session, session.current_round, deadline)
    )

    await connection_manager.broadcast_to_session(
        session.session_id,
        {
            "type": "round_updated",
            "session_id": session.session_id,
            "current_round": session.current_round,
            "current_prompt": session.current_prompt,
            "round_duration_seconds": session.round_duration_seconds,
            "round_deadline": deadline.isoformat(),
        },
    )

    return {"message": "Round timer started."}