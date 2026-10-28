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

    if session.round_timer_task is not None:
        current_task = asyncio.current_task()
        if session.round_timer_task is not current_task:
            session.round_timer_task.cancel()
        session.round_timer_task = None

    groups = session.round_groups.get(round_number, [])
    round_answers = session.group_answers.get(round_number, {})
    prompts = session.group_prompts.get(round_number, {})

    
    # Send each player only the answers from their own group.
    for group_index, group in enumerate(groups):
        answers = round_answers.get(group_index, {})

        for player_id in group:
            voting_options = [
                {
                    "player_id": answer_player_id,
                    "answer": answer,
                }
                for answer_player_id, answer in answers.items()
                if answer_player_id != player_id
            ]

            print(
                f"[VOTING] Sending to player={player_id}, "
                f"options={voting_options}"
            )

            await connection_manager.send_to_player(
                session.session_id,
                player_id,
                {
                    "type": "voting_started",
                    "session_id": session.session_id,
                    "current_round": round_number,
                    "group_index": group_index,
                    "prompt": prompts.get(group_index, ""),
                    "answers": voting_options,
                },
            )

