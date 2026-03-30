import pytest
from bot.handlers import _parse_float


def test_parse_float_valid():
    assert _parse_float("10") == 10.0
    assert _parse_float("10.5") == 10.5
    assert _parse_float("   10.5   ") == 10.5


def test_parse_float_comma():
    # Many european keyboards use comma instead of dot
    assert _parse_float("10,5") == 10.5


def test_parse_float_invalid_strings():
    assert _parse_float("abc") is None
    assert _parse_float("10.5abc") is None
    assert _parse_float("") is None
    assert _parse_float("   ") is None


def test_parse_float_negative_and_zero():
    # Only positive numbers should be allowed for shares/budget
    assert _parse_float("0") is None
    assert _parse_float("-5") is None
    assert _parse_float("-10.5") is None
