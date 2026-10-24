"""Behavioral tests for order_service.OrderService (checkout composition with injectable clock)."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

import order_service
from coupon import Coupon
from errors import InvalidCouponError, InvalidOrderError, OutOfStockError
from inventory import Inventory
from models import CouponType, CustomerLevel, OrderLine, Product
from order_service import OrderService


NOW = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
EXPIRES = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)


def fixed_clock(when=NOW):
    return lambda: when


# --- constructor: clock selection ------------------------------------------------


def test_init_defaults_clock_to_module_current_time():
    inv = Inventory([Product("A", Decimal("1.00"))], {"A": 1})
    service = OrderService(inv)
    assert service.clock is order_service.current_time
    assert service.inventory is inv


def test_init_stores_explicit_clock_object():
    custom = fixed_clock()
    inv = Inventory([Product("A", Decimal("1"))], {"A": 1})
    service = OrderService(inv, custom)
    assert service.clock is custom
    assert service.clock is not order_service.current_time


# --- checkout: successful paths ---------------------------------------------------


def test_checkout_returns_quote_and_reserves_stock():
    inv = Inventory([Product("A", Decimal("10.00"))], {"A": 5})
    service = OrderService(inv, fixed_clock())
    total = service.checkout([OrderLine("A", 2)])
    assert total == Decimal("20.00")
    assert inv.snapshot() == {"A": 3}


def test_checkout_multi_line_deducts_each_sku():
    inv = Inventory(
        [Product("A", Decimal("10")), Product("B", Decimal("22"))],
        {"A": 5, "B": 5},
    )
    service = OrderService(inv, fixed_clock())
    total = service.checkout([OrderLine("A", 1), OrderLine("B", 2)])
    assert total == Decimal("54.00")
    assert inv.snapshot() == {"A": 4, "B": 3}


def test_checkout_clock_called_exactly_once_per_attempt():
    calls = []

    def clock():
        calls.append(1)
        return NOW

    inv = Inventory([Product("A", Decimal("10.00"))], {"A": 5})
    service = OrderService(inv, clock)
    assert calls == []
    total = service.checkout([OrderLine("A", 1)])
    assert total == Decimal("10.00")
    assert len(calls) == 1


# --- checkout: pricing branches (VIP / coupon) ------------------------------------


def test_checkout_level_and_coupon_branches():
    def fresh_inventory():
        return Inventory([Product("A", Decimal("100.00"))], {"A": 10})

    # VIP with no coupon: 10% off, stock deducted.
    inv_vip = fresh_inventory()
    service_vip = OrderService(inv_vip, fixed_clock())
    assert service_vip.checkout([OrderLine("A", 1)], level=CustomerLevel.VIP) == Decimal("90.00")
    assert inv_vip.snapshot() == {"A": 9}

    # VIP with a coupon: coupon replaces VIP discount, not stacked.
    inv_coupon = fresh_inventory()
    service_coupon = OrderService(inv_coupon, fixed_clock())
    coupon = Coupon(
        kind=CouponType.FIXED,
        value=Decimal("5.00"),
        minimum=Decimal("0"),
        expires_at=EXPIRES,
    )
    total = service_coupon.checkout([OrderLine("A", 1)], level=CustomerLevel.VIP, coupon=coupon)
    assert total == Decimal("95.00")
    assert inv_coupon.snapshot() == {"A": 9}

    # REGULAR with a percent coupon: 10% of subtotal as discount.
    inv_regular = fresh_inventory()
    service_regular = OrderService(inv_regular, fixed_clock())
    percent = Coupon(
        kind=CouponType.PERCENT,
        value=Decimal("0.10"),
        minimum=Decimal("0"),
        expires_at=EXPIRES,
    )
    total = service_regular.checkout(
        [OrderLine("A", 1)], level=CustomerLevel.REGULAR, coupon=percent
    )
    assert total == Decimal("90.00")
    assert inv_regular.snapshot() == {"A": 9}


def test_checkout_fixed_coupon_exceeding_subtotal_is_floored_at_zero_and_reserves():
    inv = Inventory([Product("A", Decimal("10.00"))], {"A": 5})
    service = OrderService(inv, fixed_clock())
    coupon = Coupon(
        kind=CouponType.FIXED,
        value=Decimal("50.00"),
        minimum=Decimal("0"),
        expires_at=EXPIRES,
    )
    total = service.checkout([OrderLine("A", 1)], level=CustomerLevel.REGULAR, coupon=coupon)
    assert total == Decimal("0.00")
    assert inv.snapshot() == {"A": 4}


# --- checkout: failure leaves stock unchanged ------------------------------------


def test_checkout_unknown_sku_raises_and_leaves_stock():
    inv = Inventory([Product("A", Decimal("1"))], {"A": 5})
    service = OrderService(inv, fixed_clock())
    with pytest.raises(InvalidOrderError):
        service.checkout([OrderLine("Z", 1)])
    assert inv.snapshot() == {"A": 5}


def test_checkout_out_of_stock_raises_and_leaves_stock():
    inv = Inventory([Product("A", Decimal("10.00"))], {"A": 1})
    service = OrderService(inv, fixed_clock())
    with pytest.raises(OutOfStockError):
        service.checkout([OrderLine("A", 2)], level=CustomerLevel.REGULAR)
    assert inv.snapshot()["A"] == 1


def test_checkout_empty_lines_raises_and_leaves_stock():
    inv = Inventory([Product("A", Decimal("1"))], {"A": 5})
    service = OrderService(inv, fixed_clock())
    with pytest.raises(InvalidOrderError, match="empty order"):
        service.checkout([])
    assert inv.snapshot() == {"A": 5}


def test_checkout_invalid_level_raises_and_leaves_stock():
    inv = Inventory([Product("A", Decimal("1"))], {"A": 5})
    service = OrderService(inv, fixed_clock())
    with pytest.raises(InvalidOrderError, match="unknown customer level"):
        service.checkout([OrderLine("A", 1)], level="vip")
    assert inv.snapshot()["A"] == 5


def test_checkout_expired_coupon_raises_and_leaves_stock():
    inv = Inventory([Product("A", Decimal("100.00"))], {"A": 5})
    service = OrderService(inv, fixed_clock(EXPIRES))
    coupon = Coupon(
        kind=CouponType.FIXED,
        value=Decimal("1.00"),
        minimum=Decimal("0"),
        expires_at=EXPIRES,
    )
    with pytest.raises(InvalidCouponError, match="coupon expired"):
        service.checkout([OrderLine("A", 1)], level=CustomerLevel.VIP, coupon=coupon)
    assert inv.snapshot()["A"] == 5
