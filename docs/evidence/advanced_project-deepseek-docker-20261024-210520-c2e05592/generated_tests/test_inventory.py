"""Behavioral tests for inventory.Inventory (in-memory stock, all-or-nothing reservation)."""

from decimal import Decimal

import pytest

from errors import InvalidOrderError, OutOfStockError
from inventory import Inventory
from models import OrderLine, Product


# --- construction ----------------------------------------------------------------


def test_init_defaults_missing_stock_to_zero_and_keeps_explicit():
    p1 = Product("A", Decimal("10"))
    p2 = Product("B", Decimal("20"))
    inv = Inventory([p1, p2], {"A": 5})
    assert inv.snapshot() == {"A": 5, "B": 0}


def test_init_duplicate_sku_rejected():
    p1 = Product("A", Decimal("1"))
    p2 = Product("A", Decimal("2"))
    with pytest.raises(InvalidOrderError, match="duplicate product SKU"):
        Inventory([p1, p2], {})


def test_init_stock_unknown_sku_rejected():
    with pytest.raises(InvalidOrderError, match="stock refers to unknown SKU"):
        Inventory([Product("A", Decimal("1"))], {"Z": 1})


@pytest.mark.parametrize("amount", [-1, 1.0, True])
@pytest.mark.parametrize("amount_ignored", [None], ids=["unused"])
def test_init_invalid_stock_amount_rejected(amount, amount_ignored):
    with pytest.raises(InvalidOrderError, match="stock must be a nonnegative integer"):
        Inventory([Product("A", Decimal("1"))], {"A": amount})


def test_init_zero_stock_accepted():
    inv = Inventory([Product("A", Decimal("1"))], {"A": 0})
    assert inv.snapshot()["A"] == 0


# --- product resolution ----------------------------------------------------------


def test_product_returns_known_product():
    p = Product("A", Decimal("10"))
    inv = Inventory([p], {})
    assert inv.product("A") is p
    assert inv.product("A").sku == "A"
    assert inv.product("A").price == Decimal("10")


def test_product_unknown_sku_raises_invalid_order_error():
    inv = Inventory([Product("A", Decimal("1"))], {})
    with pytest.raises(InvalidOrderError, match="unknown SKU: MISSING") as excinfo:
        inv.product("MISSING")
    assert not isinstance(excinfo.value, OutOfStockError)


# --- snapshot isolation ----------------------------------------------------------


def test_snapshot_is_independent_copy():
    inv = Inventory([Product("A", Decimal("1"))], {"A": 5})
    snap = inv.snapshot()
    snap["A"] = 99
    snap["B"] = 1
    del snap["A"]
    assert inv.snapshot() == {"A": 5}
    assert inv.snapshot() is not inv.snapshot()


# --- reserve: rejection cases ----------------------------------------------------


def test_reserve_empty_order_rejected():
    inv = Inventory([Product("A", Decimal("1"))], {"A": 5})
    with pytest.raises(InvalidOrderError, match="empty order"):
        inv.reserve([])
    assert inv.snapshot() == {"A": 5}


def test_reserve_insufficient_stock_raises_and_keeps_stock():
    inv = Inventory([Product("A", Decimal("1"))], {"A": 5})
    with pytest.raises(OutOfStockError, match="not enough stock: A"):
        inv.reserve([OrderLine("A", 6)])
    assert inv.snapshot()["A"] == 5


def test_reserve_unknown_sku_raises_invalid_order_error():
    inv = Inventory([Product("A", Decimal("1"))], {"A": 5})
    with pytest.raises(InvalidOrderError, match="unknown SKU: Z") as excinfo:
        inv.reserve([OrderLine("Z", 1)])
    assert not isinstance(excinfo.value, OutOfStockError)
    assert inv.snapshot() == {"A": 5}


def test_reserve_aggregate_repeated_skus_exceeding_stock_keeps_stock():
    inv = Inventory([Product("A", Decimal("1"))], {"A": 5})
    with pytest.raises(OutOfStockError):
        inv.reserve([OrderLine("A", 4), OrderLine("A", 2)])
    assert inv.snapshot()["A"] == 5


def test_reserve_is_all_or_nothing_across_skus():
    inv = Inventory(
        [Product("A", Decimal("1")), Product("B", Decimal("1"))],
        {"A": 5, "B": 1},
    )
    with pytest.raises(OutOfStockError):
        inv.reserve([OrderLine("A", 2), OrderLine("B", 2)])
    assert inv.snapshot() == {"A": 5, "B": 1}


# --- reserve: successful deduction -----------------------------------------------


def test_reserve_deducts_sufficient_stock():
    inv = Inventory([Product("A", Decimal("1"))], {"A": 5})
    inv.reserve([OrderLine("A", 3)])
    assert inv.snapshot()["A"] == 2


def test_reserve_exact_available_quantity_leaves_zero():
    inv = Inventory([Product("A", Decimal("1"))], {"A": 5})
    inv.reserve([OrderLine("A", 5)])
    assert inv.snapshot()["A"] == 0


def test_reserve_aggregates_repeated_skus_within_stock():
    inv = Inventory([Product("A", Decimal("1"))], {"A": 5})
    inv.reserve([OrderLine("A", 2), OrderLine("A", 3)])
    assert inv.snapshot()["A"] == 0


def test_reserve_multi_sku_deduction():
    inv = Inventory(
        [Product("A", Decimal("1")), Product("B", Decimal("1"))],
        {"A": 5, "B": 2},
    )
    inv.reserve([OrderLine("A", 1), OrderLine("B", 2)])
    assert inv.snapshot() == {"A": 4, "B": 0}


def test_post_reserve_read_access_reflects_new_stock():
    inv = Inventory([Product("A", Decimal("10"))], {"A": 5})
    inv.reserve([OrderLine("A", 2)])
    assert inv.product("A").sku == "A"
    assert inv.snapshot() == {"A": 3}
