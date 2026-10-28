import pytest

from backend.app.sessions.session import Session

def test_mod_player():
    session = Session("123456")
    session.add_player("player1", "Alice")
    session.add_player("player2", "Bob")
    session.mod_player("player1", True)
    assert session.players["player1"].is_mod == True

def test_unmod_player():
    session = Session("123456")
    session.add_player("player1", "Alice")
    session.add_player("player2", "Bob")
    session.mod_player("player1", True)
    session.mod_player("player1", False)
    assert session.players["player1"].is_mod == False
