import asyncio

from backend.app.websockets.connection_manager import connection_manager



async def start_voting(session, round_number: int) -> None:
    print(
        f"[VOTING] Called: phase={session.phase}, "
        f"round={round_number}, session={session.session_id}"
    )

    if session.phase != "answering":
        print(f"[VOTING] Returning because phase is {session.phase!r}")
        return

    groups = session.round_groups.get(round_number, [])
    round_answers = session.group_answers.get(round_number, {})
    prompts = session.group_prompts.get(round_number, {})

    print(f"[VOTING] Groups: {groups}")
    print(f"[VOTING] Answers: {round_answers}")
    print(f"[VOTING] Prompts: {prompts}")

    session.phase = "voting"
    session.round_deadline = None
    session.log_event("voting_started", f"Voting opened for round {round_number}.")

    if session.round_timer_task is not None:
        current_task = asyncio.current_task()
        if session.round_timer_task is not current_task:
            session.round_timer_task.cancel()
        session.round_timer_task = None

    await send_voting_options(session, round_number, list(session.players))


async def send_voting_options(session, round_number: int, player_ids: list[str]) -> None:
    """Send each player the answers from every OTHER group."""
    groups = session.round_groups.get(round_number, [])
    round_answers = session.group_answers.get(round_number, {})
    prompts = session.group_prompts.get(round_number, {})

    for player_id in player_ids:
        try:
            voter_group_index = session.get_player_group_index(
                round_number,
                player_id,
            )
        except ValueError:
            # Late joiners waiting for the next round aren't in a group yet.
            continue

        voting_options_by_group = []

        for group_index, group in enumerate(groups):
            answers = round_answers.get(group_index, {})

            # Kicks can leave a group with nothing to vote on.
            if group_index == voter_group_index or not answers:
                continue

            voting_options_by_group.append(
                {
                    "group_index": group_index,
                    "prompt": prompts.get(group_index, ""),
                    "answers": [
                        {
                            "player_id": answer_player_id,
                            "answer": answer,
                        }
                        for answer_player_id, answer in answers.items()
                        if answer_player_id != player_id
                    ],
                }
            )

        await connection_manager.send_to_player(
            session.session_id,
            player_id,
            {
                "type": "voting_started",
                "session_id": session.session_id,
                "current_round": round_number,
                "groups": voting_options_by_group,
            },
        )


async def resume_round_after_kick(session) -> None:
    """Keep a Quiplash round moving once a kicked player is out of it."""
    round_number = session.current_round

    if session.phase == "answering" and session.all_players_submitted(round_number):
        # The kicked player was the only one everyone was still waiting on.
        await start_voting(session, round_number)

    elif session.phase == "voting":
        # Re-send ballots without the kicked answer to anyone who hasn't voted yet.
        voted = {
            voter_id
            for votes in session.group_votes.get(round_number, {}).values()
            for voter_id in votes
        }
        await send_voting_options(
            session,
            round_number,
            [player_id for player_id in session.players if player_id not in voted],
        )

