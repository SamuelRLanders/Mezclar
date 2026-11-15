"""
Routes for the Keywords game.

Players act through the POST routes below. After every successful action, each
player in the affected group is sent their own private view over the websocket,
and the host is pinged to refresh. All game rules live in KeywordsGame; these
routes only look up the game, call it, and send out the results.
"""

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.routes_host import require_host
from backend.app.games.keywords.game import KeywordsGame, KeywordsGroup
from backend.app.models.schemas import KeywordsActionRequest, KeywordsSubmitRequest
from backend.app.sessions.registry import get_session
from backend.app.sessions.session import Session
from backend.app.websockets.connection_manager import connection_manager
from backend.app.websockets.handlers import send_keywords_state

router = APIRouter()


def require_keywords_game(session_id: str) -> tuple[Session, KeywordsGame]:
    # Look up the session and make sure it is running a Keywords game.
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.game_id != "keywords" or session.keywords is None:
        raise HTTPException(status_code=400, detail="This session is not running a Keywords game.")
    return session, session.keywords


async def broadcast_group(session: Session, group: KeywordsGroup) -> None:
    """
    Send every member of the group their own updated view, then ping the host.
    Each player gets a different message, because each view hides different secrets.
    """
    for player_id in group.player_ids:
        await send_keywords_state(session, player_id)

    # The host page refetches the full host view when it gets any message.
    await connection_manager.broadcast_to_session(
        session.session_id,
        {"type": "keywords_updated", "group_index": group.index},
        host_only=True,
    )


async def apply_action(
    session: Session,
    player_id: str,
    action: Callable[[str], KeywordsGroup],
) -> dict:
    """
    Shared steps for every player action: run it, log a phase change, notify the
    group and the host, and return the player's new view. The response carries the
    view too, so the player's screen updates even if their websocket is slow.
    """
    game = session.keywords
    try:
        # Remember the phase so we can tell whether this action moved the group on.
        phase_before = game.group_for(player_id).phase
        group = action(player_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    # Record phase changes in the host's game log.
    if group.phase != phase_before:
        session.log_event("keywords_phase", f"{group.label} group moved to {group.phase}.")

    # Once every group has revealed, the whole game is over.
    if game.is_finished and session.phase != "finished":
        session.phase = "finished"
        session.log_event("game_finished", "The game finished.")

    await broadcast_group(session, group)
    return game.player_view(player_id)


@router.get("/session/{session_id}/keywords/state")
def keywords_state(session_id: str, player_id: str) -> dict:
    # A player's current view, for first page load and refresh.
    _session, game = require_keywords_game(session_id)
    try:
        return game.player_view(player_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/session/{session_id}/keywords/ready")
async def keywords_ready(session_id: str, request: KeywordsActionRequest) -> dict:
    # Gathering (US 61): the player has found their group.
    session, game = require_keywords_game(session_id)
    return await apply_action(session, request.player_id, game.mark_ready)


@router.post("/session/{session_id}/keywords/role-seen")
async def keywords_role_seen(session_id: str, request: KeywordsActionRequest) -> dict:
    # Roles (US 62): the player has read their role.
    session, game = require_keywords_game(session_id)
    return await apply_action(session, request.player_id, game.mark_role_seen)


@router.post("/session/{session_id}/keywords/word-said")
async def keywords_word_said(session_id: str, request: KeywordsActionRequest) -> dict:
    # Speaking (US 63): the current speaker has said their word.
    session, game = require_keywords_game(session_id)
    return await apply_action(session, request.player_id, game.mark_word_said)


@router.post("/session/{session_id}/keywords/submit")
async def keywords_submit(session_id: str, request: KeywordsSubmitRequest) -> dict:
    # Voting (US 64): a suspect's name, or the faker's keyword guess. Same route for both.
    session, game = require_keywords_game(session_id)
    return await apply_action(
        session,
        request.player_id,
        lambda player_id: game.submit_answer(player_id, request.text),
    )


@router.get("/session/{session_id}/keywords/host-state")
def keywords_host_state(session_id: str, session: Session = Depends(require_host)) -> dict:
    # Everything about every group, including keywords and fakers. Requires the host token.
    _session, game = require_keywords_game(session_id)
    return game.host_view()
