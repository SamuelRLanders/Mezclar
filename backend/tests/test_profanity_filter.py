import pytest

from backend.app.naming.generator import validate_name

def test_does_not_crash_on_empty_string():
    assert validate_name("") == True

def test_does_not_allow_profane_name():
    assert validate_name("jerk") == False

def test_does_not_allow_profane_name_with_spaces():
    assert validate_name("jerk face") == False

def test_does_not_allow_profane_name_with_mixed_case():
    assert validate_name("JeRk") == False

def test_allows_non_profane_name():
    assert validate_name("friendly") == True