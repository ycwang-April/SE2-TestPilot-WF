import pytest

from discount import discount_rate


@pytest.mark.parametrize(
    "total",
    [0, 50, 99.99, 100.0, 100.01, 150, 1000],
)
def test_member_gets_twenty_percent_regardless_of_total(total):
    assert discount_rate(total, member=True) == 0.2


def test_member_precedence_over_high_total_returns_member_rate():
    assert discount_rate(500, member=True) == 0.2


def test_non_member_at_exact_threshold_gets_ten_percent():
    assert discount_rate(100.0) == 0.1


@pytest.mark.parametrize(
    "total, expected",
    [
        (99.99, 0.0),
        (100.01, 0.1),
    ],
)
def test_non_member_threshold_sides(total, expected):
    assert discount_rate(total, member=False) == expected


@pytest.mark.parametrize("total", [0, 50])
def test_non_member_below_threshold_returns_zero_discount(total):
    assert discount_rate(total) == 0.0


@pytest.mark.parametrize("total", [150, 1000])
def test_non_member_above_threshold_returns_ten_percent(total):
    assert discount_rate(total, member=False) == 0.1


@pytest.mark.parametrize(
    "total, member",
    [
        (-1, False),
        (-1, True),
        (-0.01, False),
    ],
)
def test_negative_total_raises_value_error(total, member):
    with pytest.raises(ValueError, match="negative total"):
        discount_rate(total, member=member)


def test_negative_total_member_raises_before_membership_branch():
    with pytest.raises(ValueError, match="negative total"):
        discount_rate(-50, member=True)
