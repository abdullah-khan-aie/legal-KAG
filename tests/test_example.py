"""Smoke test for the placeholder module."""

from lodestone_spg.example import add


def test_add() -> None:
    """add() retuurns the arithimetic sum"""
    assert add(1, 2) == 3
