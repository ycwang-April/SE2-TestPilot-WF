import pytest

from models import Item


@pytest.mark.parametrize(
    "price, quantity, expected",
    [
        (10.0, 3, 30.0),
        (2.5, 4, 10.0),
        (0.5, 7, 3.5),
    ],
)
def test_subtotal_returns_price_times_quantity(price, quantity, expected):
    assert Item(price=price, quantity=quantity).subtotal() == expected


def test_default_quantity_is_one_and_subtotal_equals_price():
    item = Item(price=19.99)
    assert item.quantity == 1
    assert item.subtotal() == 19.99


@pytest.mark.parametrize(
    "price, quantity",
    [
        (0.0, 5),
        (10.0, 0),
        (0.0, 0),
    ],
)
def test_zero_values_produce_zero_subtotal_without_raising(price, quantity):
    assert Item(price=price, quantity=quantity).subtotal() == 0.0


@pytest.mark.parametrize(
    "price, quantity",
    [
        (-0.01, 1),
        (-5.0, 2),
        (-100.0, 3),
    ],
)
def test_negative_price_raises_value_error(price, quantity):
    with pytest.raises(ValueError, match="negative price or quantity"):
        Item(price=price, quantity=quantity).subtotal()


@pytest.mark.parametrize(
    "price, quantity",
    [
        (10.0, -1),
        (2.5, -10),
    ],
)
def test_negative_quantity_raises_value_error(price, quantity):
    with pytest.raises(ValueError, match="negative price or quantity"):
        Item(price=price, quantity=quantity).subtotal()


def test_both_price_and_quantity_negative_raise_single_value_error():
    with pytest.raises(ValueError, match="negative price or quantity"):
        Item(price=-1.0, quantity=-2).subtotal()


def test_validation_happens_at_call_time_not_construction():
    item = Item(price=5.0, quantity=-1)
    with pytest.raises(ValueError, match="negative price or quantity"):
        item.subtotal()


def test_mutated_negative_quantity_makes_next_subtotal_raise():
    item = Item(price=3.0, quantity=2)
    assert item.subtotal() == 6.0
    item.quantity = -1
    with pytest.raises(ValueError, match="negative price or quantity"):
        item.subtotal()
