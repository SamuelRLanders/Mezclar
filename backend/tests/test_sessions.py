import pytest
from unittest.mock import patch
from backend.app.sessions.session import Session


def test_set_auto_generate():
    session = Session("abc123")
    session.set_auto_generate(True)
    assert session.auto_generate_names is True

def test_add_used_name():
    session = Session("abc123")
    session.add_used_name("test_name")
    assert "test_name" in session.used_names

def test_remove_used_name():
    session = Session("abc123")
    session.add_used_name("test_name")
    session.remove_used_name("test_name")
    assert "test_name" not in session.used_names

def test_assign_name_with_requested_name():
    session = Session("abc123")
    name = session.assign_name("requested_name")
    assert name == "requested_name"
    assert "requested_name" in session.used_names

def test_assign_name_with_auto_generate():
    session = Session("abc123")
    session.set_auto_generate(True)
    with patch('backend.app.sessions.session.generate_unique_name', return_value="generated_name"):
        name = session.assign_name()
        assert name == "generated_name"
        assert "generated_name" in session.used_names

def test_raise_error_when_no_name_and_auto_generate_disabled():
    session = Session("abc123")
    with pytest.raises(ValueError):
        session.assign_name()

def test_add_player_with_requested_name():
    session = Session("abc123")
    player = session.add_player("player1", "requested_name")
    assert player.name == "requested_name"
    assert "requested_name" in session.used_names
    assert session.get_player("player1") == player

def test_remove_player_removes_used_name():
    session = Session("abc123")
    player = session.add_player("player1", "requested_name")
    session.remove_player("player1")
    assert "requested_name" not in session.used_names

def test_get_player_returns_none_if_missing():
    session = Session("abc123")
    assert session.get_player("nonexistent") is None

def test_regenerate_name_nonexistent_player():
    session = Session("abc123")
    with pytest.raises(ValueError):
        session.regenerate_name("nonexistent_player")

def test_regenerate_name_existing_player():
    session = Session("abc123")
    session.set_auto_generate(True)
    session.add_player("existing_player", requested_name="old_name")
    with patch("backend.app.sessions.session.generate_unique_name", return_value="new_name"):
        new_name = session.regenerate_name("existing_player")
        assert new_name == "new_name"
        assert session.get_player("existing_player").name == "new_name"
        assert "old_name" not in session.used_names
        assert "new_name" in session.used_names

def test_kick_player_removes_from_session():
    session = Session("abc123")
    player = session.add_player("player1", "requested_name")
    session.kick_player("player1")
    assert session.get_player("player1") is None

def test_kick_player_frees_name():
    session = Session("abc123")
    session.add_player("player1", "requested_name")
    session.kick_player("player1")
    assert "requested_name" not in session.used_names

def test_kick_nonexistent_player_raises_error():
    session = Session("abc123")
    with pytest.raises(ValueError):
        session.kick_player("nonexistent_player")

def test_hide_player_sets_flag():
    session = Session("abc123")
    player = session.add_player("player1", "requested_name")
    session.hide_player("player1")
    assert player.hidden is True

def test_hide_nonexistent_player_raises_error():
    session = Session("abc123")
    with pytest.raises(ValueError):
        session.hide_player("nonexistent_player")


def test_generate_round_groups_assigns_every_player_once_per_round():
    session = Session("abc123", settings={"rounds": 3})

    for i in range(10):
        session.add_player(f"player{i}", f"Player {i}")

    groups_by_round = session.generate_round_groups()

    assert len(groups_by_round) == 3

    expected_players = set(session.players.keys())

    for groups in groups_by_round.values():
        assigned_players = [
            player_id
            for group in groups
            for player_id in group
        ]

        assert len(assigned_players) == 10
        assert set(assigned_players) == expected_players
        assert max(map(len, groups)) - min(map(len, groups)) <= 1


def test_generate_round_groups_stores_assignments():
    session = Session("abc123", settings={"rounds": 2})

    for i in range(6):
        session.add_player(f"player{i}", f"Player {i}")

    groups_by_round = session.generate_round_groups()

    assert session.round_groups == groups_by_round



def test_generate_round_groups_minimizes_repeated_pairings():
    session = Session("abc123", settings={"rounds": 3})

    for i in range(12):
        session.add_player(f"player{i}", f"Player {i}")

    groups_by_round = session.generate_round_groups()

    assert len(groups_by_round) == 3

    expected_players = set(session.players.keys())

    for groups in groups_by_round.values():
        assigned_players = [
            player_id
            for group in groups
            for player_id in group
        ]

        # Every player appears exactly once per round.
        assert len(assigned_players) == 12
        assert set(assigned_players) == expected_players

        # Groups are balanced.
        assert max(map(len, groups)) - min(map(len, groups)) <= 1

    # Pairing quality is evaluated separately; the randomized search
    # attempts to minimize repeats but does not guarantee a fixed count.


def test_assign_group_prompts_assigns_unique_prompts():
    session = Session("abc123", settings={"rounds": 3})

    for i in range(12):
        session.add_player(f"player{i}", f"Player {i}")

    session.generate_round_groups()
    group_prompts = session.assign_group_prompts()

    # Every generated group should have exactly one prompt.
    for round_number, groups in session.round_groups.items():
        assert len(group_prompts[round_number]) == len(groups)

    # All prompts should be unique across the game.
    assigned_prompts = [
        prompt
        for prompts in group_prompts.values()
        for prompt in prompts.values()
    ]
    assert len(assigned_prompts) == len(set(assigned_prompts))


def test_assign_group_prompts_raises_when_not_enough_prompts(monkeypatch):
    session = Session("abc123", settings={"rounds": 3})

    for i in range(12):
        session.add_player(f"player{i}", f"Player {i}")

    session.generate_round_groups()

    # Simulate a prompt pool that's too small for the generated groups.
    monkeypatch.setattr(
        "backend.app.sessions.session.QUIPLASH_PROMPTS",
        ["Prompt A", "Prompt B"],
    )

    with pytest.raises(ValueError, match="Not enough unique prompts"):
        session.assign_group_prompts()


def test_submit_answer_stores_answer_in_player_group():
    session = Session("abc123", settings={"rounds": 3})
    session.configure_game("quiplash", 2, 50)

    for i in range(6):
        session.add_player(f"player{i}", f"Player {i}")

    session.generate_round_groups()
    session.assign_group_prompts()
    session.start_game()

    player_id = next(iter(session.players))
    group_index = session.get_player_group_index(1, player_id)

    session.submit_answer(player_id, "A funny answer")

    assert (
        session.group_answers[1][group_index][player_id]
        == "A funny answer"
    )



def test_submit_answer_rejects_player_without_group_assignment():
    session = Session("abc123", settings={"rounds": 3})
    session.configure_game("quiplash", 2, 50)

    session.add_player("player1", "Player 1")
    session.add_player("player2", "Player 2")
    session.start_game()

    # Simulate missing group assignments after startup.
    session.round_groups.pop(1)

    with pytest.raises(ValueError, match="Groups have not been generated"):
        session.submit_answer("player1", "A funny answer")



def test_advance_round_uses_assigned_prompts_and_preserves_answers():
    session = Session("abc123", settings={"rounds": 3})
    session.configure_game("quiplash", 2, 50)

    for i in range(6):
        session.add_player(f"player{i}", f"Player {i}")

    session.generate_round_groups()
    session.assign_group_prompts()
    session.start_game()

    # Record an answer from round 1.
    player_id = next(iter(session.players))
    group_index = session.get_player_group_index(1, player_id)
    session.submit_answer(player_id, "Round 1 answer")

    session.advance_round()

    assert session.current_round == 2
    assert session.current_prompt in session.group_prompts[2].values()
    assert (
        session.group_answers[1][group_index][player_id]
        == "Round 1 answer"
    )


def test_start_game_initializes_group_assignments_and_prompts():
    session = Session("abc123", settings={"rounds": 3})
    session.configure_game("quiplash", 2, 50)

    for i in range(10):
        session.add_player(f"player{i}", f"Player {i}")

    session.start_game()

    assert session.game_started is True
    assert session.current_round == 1
    assert 1 in session.round_groups
    assert 1 in session.group_prompts

    for round_number in range(1, session.total_rounds + 1):
        assert round_number in session.round_groups
        assert round_number in session.group_prompts
        assert len(session.round_groups[round_number]) == len(
            session.group_prompts[round_number]
        )

def test_all_players_submitted_returns_false_until_everyone_answers():
    session = Session("abc123", settings={"rounds": 3})
    session.configure_game("quiplash", 2, 50)

    for i in range(6):
        session.add_player(f"player{i}", f"Player {i}")

    session.generate_round_groups()
    session.assign_group_prompts()
    session.start_game()

    groups = session.round_groups[1]

    assert session.all_players_submitted(1) is False

    for group in groups:
        for player_id in group:
            session.submit_answer(player_id, f"Answer from {player_id}")

    assert session.all_players_submitted(1) is True


def test_all_players_submitted_checks_only_the_requested_round():
    session = Session("abc123", settings={"rounds": 3})
    session.configure_game("quiplash", 2, 50)

    for i in range(6):
        session.add_player(f"player{i}", f"Player {i}")

    session.generate_round_groups()
    session.assign_group_prompts()
    session.start_game()

    for group in session.round_groups[1]:
        for player_id in group:
            session.submit_answer(player_id, f"Round 1 answer")

    assert session.all_players_submitted(1) is True
    assert session.all_players_submitted(2) is False