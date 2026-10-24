import pytest

from models import Item
from order import order_total


@pytest.mark.parametrize(
    "items, expected",
    [
        ([Item(10.0, 2), Item(5.0, 1)], 25.0),
        ([Item(20.0, 3)], 60.0),
    ],
)
def test_non_member_below_threshold_has_no_discount(items, expected):
    assert order_total(items, member=False) == expected


@pytest.mark.parametrize(
    "items, expected",
    [
        ([Item(50.0, 3)], 135.0),
        ([Item(120.0, 1)], 108.0),
    ],
)
def test_non_member_above_threshold_gets_ten_percent_discount(items, expected):
    assert order_total(items, member=False) == expected


@pytest.mark.parametrize(
    "items, expected",
    [
        ([Item(50.0, 1)], 40.0),
        ([Item(100.0, 2)], 160.0),
    ],
)
def test_member_gets_twenty_percent_discount_regardless_of_total(items, expected):
    assert order_total(items, member=True) == expected


def test_non_member_total_exactly_at_threshold_gets_ten_percent_discount():
    assert order_total([Item(100.0, 1)], member=False) == 90.0


def test_non_member_total_just_below_threshold_gets_no_discount():
    assert order_total([Item(99.99, 1)], member=False) == 99.99


def test_empty_item_list_returns_zero_total():
    assert order_total([]) == 0.0


def test_subthreshold_total_is_rounded_to_two_decimals():
    assert order_total([Item(33.333, 1)], member=False) == 33.33


def test_negative_item_price_propagates_value_error():
    with pytest.raises(ValueError, match="negative price or quantity"):
        order_total([Item(10.0, 1), Item(-5.0, 1)], member=False)


def test_negative_item_price_raises_even_for_member_order():
    with pytest.raises(ValueError, match="negative price or quantity"):
        order_total([Item(-1.0, 1)], member=True)


def test_single_member_item_with_zero_subtotal_returns_zero():
    assert order_total([Item(0.0, 0)], member=True) == 0.0


def test_order_total_uses_item_subtotal_quantity_product():
    assert order_total([Item(10.0, 3)], member=False) == 30.0
