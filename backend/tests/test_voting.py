
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

    payloads = [
        call.args[2]
        for call in broadcast.await_args_list
    ]

    assert all(payload["type"] == "voting_started" for payload in payloads)
    assert all(payload["current_round"] == 1 for payload in payloads)

    # Every player should receive only their own group's answers,
    # excluding their own answer.
    for payload in payloads:
        group_index = payload["group_index"]
        group = session.round_groups[1][group_index]
        recipient_id = next(
            player_id
            for player_id in group
            if all(
                option["player_id"] != player_id
                for option in payload["answers"]
            )
        )
        assert all(
            option["player_id"] in group
            for option in payload["answers"]
        )
        assert all(
            option["player_id"] != recipient_id
            for option in payload["answers"]
        )


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
