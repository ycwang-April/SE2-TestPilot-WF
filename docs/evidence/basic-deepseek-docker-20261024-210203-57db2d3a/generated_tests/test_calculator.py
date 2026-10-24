"""Behavioral tests for calculator contracts."""

import pytest

from calculator import clamp, divide


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (10, 2, 5.0),
        (10, 4, 2.5),
        (-9, 3, -3.0),
        (1, 2, 0.5),
    ],
)
def test_divide_normal_quotient(a, b, expected):
    result = divide(a, b)
    assert result == expected
    assert isinstance(result, float)


@pytest.mark.parametrize("a", [1.0, -1.0, 0.0])
def test_divide_zero_divisor_raises(a):
    with pytest.raises(ValueError, match="divisor must not be zero"):
        divide(a, 0)


def test_clamp_below_lower_returns_lower():
    assert clamp(0.0, 1.0, 5.0) == 1.0


def test_clamp_above_upper_returns_upper():
    assert clamp(10.0, 1.0, 5.0) == 5.0


def test_clamp_within_range_returns_value():
    assert clamp(3.0, 1.0, 5.0) == 3.0


@pytest.mark.parametrize(
    "value, lower, upper",
    [
        (1.0, 1.0, 5.0),
        (5.0, 1.0, 5.0),
    ],
)
def test_clamp_inclusive_bounds_return_value(value, lower, upper):
    assert clamp(value, lower, upper) == value


def test_clamp_inverted_bounds_raise():
    with pytest.raises(ValueError, match="lower exceeds upper"):
        clamp(2.0, 5.0, 1.0)


def test_clamp_equal_bounds_returns_shared_bound():
    assert clamp(3.0, 5.0, 5.0) == 5.0
