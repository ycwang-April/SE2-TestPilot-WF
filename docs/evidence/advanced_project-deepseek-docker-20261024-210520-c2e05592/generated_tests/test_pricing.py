"""Behavioral tests for pricing.quote (coupon replaces VIP, floor at zero, single ROUND_HALF_UP)."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from coupon import Coupon
from errors import InvalidCouponError, InvalidOrderError, OutOfStockError
from inventory import Inventory
from models import CouponType, CustomerLevel, OrderLine, Product
from pricing import quote


NOW = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
EXPIRES = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)


def make_inventory():
    return Inventory([Product("A", Decimal("10.00"))], {"A": 5})


def fixed_coupon(value, minimum=Decimal("0"), expires_at=EXPIRES):
    return Coupon(kind=CouponType.FIXED, value=value, minimum=minimum, expires_at=expires_at)


def percent_coupon(value, minimum=Decimal("0"), expires_at=EXPIRES):
    return Coupon(kind=CouponType.PERCENT, value=value, minimum=minimum, expires_at=expires_at)


# --- normal pricing ----------------------------------------------------------------


def test_regular_no_coupon_returns_subtotal_cents():
    inv = make_inventory()
    total = quote([OrderLine("A", 2)], inv, CustomerLevel.REGULAR, None, NOW)
    assert total == Decimal("20.00")
    assert isinstance(total, Decimal)


def test_vip_no_coupon_applies_ten_percent_off():
    inv = Inventory([Product("A", Decimal("100.00"))], {"A": 5})
    total = quote([OrderLine("A", 1)], inv, CustomerLevel.VIP, None, NOW)
    assert total == Decimal("90.00")


def test_multi_line_subtotal_sums_price_times_quantity():
    inv = Inventory(
        [Product("A", Decimal("10.00")), Product("B", Decimal("22.00"))],
        {"A": 5, "B": 5},
    )
    total = quote([OrderLine("A", 1), OrderLine("B", 2)], inv, CustomerLevel.REGULAR, None, NOW)
    assert total == Decimal("54.00")


def test_repeated_sku_lines_are_priced_independently():
    inv = Inventory([Product("A", Decimal("4.00"))], {"A": 5})
    total = quote([OrderLine("A", 2), OrderLine("A", 3)], inv, CustomerLevel.REGULAR, None, NOW)
    assert total == Decimal("20.00")


# --- rounding boundary -------------------------------------------------------------


def test_round_half_up_at_half_cent_boundary():
    inv = Inventory([Product("A", Decimal("0.05"))], {"A": 5})
    total = quote([OrderLine("A", 1)], inv, CustomerLevel.VIP, None, NOW)
    assert total == Decimal("0.05")
    assert total != Decimal("0.04")


def test_single_rounding_after_fractional_percent_discount():
    inv = Inventory([Product("A", Decimal("10.05"))], {"A": 5})
    total = quote([OrderLine("A", 1)], inv, CustomerLevel.REGULAR, percent_coupon(Decimal("0.33")), NOW)
    assert total == Decimal("6.73")


# --- coupon branches ---------------------------------------------------------------


def test_coupon_replaces_vip_discount_even_when_less_generous():
    inv = Inventory([Product("A", Decimal("100.00"))], {"A": 5})
    total = quote(
        [OrderLine("A", 1)],
        inv,
        CustomerLevel.VIP,
        fixed_coupon(Decimal("5.00")),
        NOW,
    )
    assert total == Decimal("95.00")


def test_regular_with_percent_coupon_subtracts_percentage():
    inv = Inventory([Product("A", Decimal("80.00"))], {"A": 5})
    total = quote(
        [OrderLine("A", 1)],
        inv,
        CustomerLevel.REGULAR,
        percent_coupon(Decimal("0.25")),
        NOW,
    )
    assert total == Decimal("60.00")


def test_coupon_accepted_strictly_before_exclusive_expiry():
    inv = Inventory([Product("A", Decimal("100.00"))], {"A": 5})
    now = datetime(2025, 1, 1, 11, 59, 59, 999999, tzinfo=timezone.utc)
    total = quote(
        [OrderLine("A", 1)],
        inv,
        CustomerLevel.REGULAR,
        fixed_coupon(Decimal("5.00")),
        now,
    )
    assert total == Decimal("95.00")


# --- floor at zero -----------------------------------------------------------------


def test_fixed_coupon_exceeding_subtotal_floors_at_zero():
    inv = make_inventory()
    total = quote(
        [OrderLine("A", 1)],
        inv,
        CustomerLevel.REGULAR,
        fixed_coupon(Decimal("50.00")),
        NOW,
    )
    assert total == Decimal("0.00")


def test_fixed_coupon_equal_to_subtotal_yields_zero():
    inv = make_inventory()
    total = quote(
        [OrderLine("A", 1)],
        inv,
        CustomerLevel.REGULAR,
        fixed_coupon(Decimal("10.00")),
        NOW,
    )
    assert total == Decimal("0.00")


# --- quote never reserves ----------------------------------------------------------


def test_quote_does_not_reserve_stock():
    inv = make_inventory()
    before = inv.snapshot()
    total = quote([OrderLine("A", 3)], inv, CustomerLevel.REGULAR, None, NOW)
    assert total == Decimal("30.00")
    assert inv.snapshot() == before == {"A": 5}


# --- invalid inputs ----------------------------------------------------------------


def test_empty_lines_raises_invalid_order_error():
    inv = make_inventory()
    with pytest.raises(InvalidOrderError, match="empty order"):
        quote([], inv, CustomerLevel.REGULAR, None, NOW)


@pytest.mark.parametrize("level", ["vip", "regular", None, 1])
def test_invalid_customer_level_rejected(level):
    inv = make_inventory()
    with pytest.raises(InvalidOrderError, match="unknown customer level"):
        quote([OrderLine("A", 1)], inv, level, None, NOW)


def test_empty_lines_check_precedes_level_check():
    inv = make_inventory()
    with pytest.raises(InvalidOrderError, match="empty order"):
        quote([], inv, "vip", None, NOW)


def test_unknown_sku_raises_invalid_order_error_not_out_of_stock():
    inv = make_inventory()
    with pytest.raises(InvalidOrderError, match="unknown SKU: Z") as excinfo:
        quote([OrderLine("Z", 1)], inv, CustomerLevel.REGULAR, None, NOW)
    assert not isinstance(excinfo.value, OutOfStockError)


# --- coupon errors propagate (never fall back to VIP) -------------------------------


def test_expired_coupon_propagates_without_vip_fallback():
    inv = Inventory([Product("A", Decimal("100.00"))], {"A": 5})
    coupon = fixed_coupon(Decimal("5.00"), expires_at=NOW)
    with pytest.raises(InvalidCouponError, match="coupon expired"):
        quote([OrderLine("A", 1)], inv, CustomerLevel.VIP, coupon, NOW)


def test_coupon_below_minimum_spend_propagates():
    inv = Inventory([Product("A", Decimal("40.00"))], {"A": 5})
    coupon = fixed_coupon(Decimal("5.00"), minimum=Decimal("50.00"))
    with pytest.raises(InvalidCouponError, match="minimum spend not met"):
        quote([OrderLine("A", 1)], inv, CustomerLevel.REGULAR, coupon, NOW)
