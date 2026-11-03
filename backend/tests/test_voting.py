
import asyncio
from unittest.mock import AsyncMock, call, patch

from backend.app.api.voting import start_voting
from backend.app.sessions.session import Session


def create_started_session() -> Session:
    session = Session("abc123", settings={"rounds": 3})
    session.configure_game("quiplash", 2, 50)

    for i in range(6):
        session.add_player(f"player{i}", f"Player {i}")

    session.start_game()
    return session


def test_start_voting_changes_phase_and_broadcasts_answers():
    session = create_started_session()
    session.phase = "answering"

    group_index = 0
    player_id = session.round_groups[1][group_index][0]
    session.group_answers.setdefault(1, {})[group_index] = {
        player_id: "A funny answer",
    }

    with patch(
        "backend.app.api.voting.connection_manager.send_to_player",
        new_callable=AsyncMock,
    ) as broadcast:
        asyncio.run(start_voting(session, 1))

    assert session.phase == "voting"
    assert session.round_deadline is None
    assert broadcast.await_count == len(session.players)

    ballots = {
        call.args[1]: call.args[2]
        for call in broadcast.await_args_list
    }

    assert set(ballots) == set(session.players)
    assert all(payload["type"] == "voting_started" for payload in ballots.values())
    assert all(payload["current_round"] == 1 for payload in ballots.values())

    # Players vote on every OTHER group's answers; groups with no answers are skipped.
    # Only group 0 answered, so its members get nothing to vote on and everyone else gets group 0.
    for recipient_id, payload in ballots.items():
        if recipient_id in session.round_groups[1][group_index]:
            assert payload["groups"] == []
        else:
            assert payload["groups"] == [{
                "group_index": group_index,
                "prompt": session.group_prompts[1][group_index],
                "answers": [{"player_id": player_id, "answer": "A funny answer"}],
            }]


def test_start_voting_does_not_broadcast_twice():
    session = create_started_session()
    session.phase = "voting"

    with patch(
        "backend.app.api.voting.connection_manager.send_to_player",
        new_callable=AsyncMock,
    ) as broadcast:
        asyncio.run(start_voting(session, 1))

    broadcast.assert_not_awaited()


def test_start_voting_cancels_existing_timer():
    session = create_started_session()
    session.phase = "answering"

    async def dummy_timer():
        await asyncio.sleep(60)

    async def run_test():
        session.round_timer_task = asyncio.create_task(dummy_timer())

        with patch(
            "backend.app.api.voting.connection_manager.send_to_player",
            new_callable=AsyncMock,
        ):
            await start_voting(session, 1)

        assert session.phase == "voting"
        assert session.round_timer_task is None
        assert session.round_deadline is None

        # Allow the canceled timer task to process cancellation.
        await asyncio.sleep(0)
        assert session.round_timer_task is None

    asyncio.run(run_test())
