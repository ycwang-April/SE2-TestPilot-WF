"""Behavioral tests for coupon.Coupon.discount."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from coupon import Coupon
from errors import InvalidCouponError
from models import CouponType


EXPIRES = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
NOW_BEFORE = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)


def make_coupon(kind=CouponType.FIXED, value=Decimal("5.00"), minimum=Decimal("0.00"), expires_at=EXPIRES):
    return Coupon(kind=kind, value=value, minimum=minimum, expires_at=expires_at)


# --- normal discount computation -------------------------------------------------


def test_fixed_returns_value_above_minimum():
    coupon = make_coupon(kind=CouponType.FIXED, value=Decimal("5.00"), minimum=Decimal("20.00"))
    assert coupon.discount(Decimal("100.00"), NOW_BEFORE) == Decimal("5.00")


def test_percent_multiplies_subtotal_by_fraction():
    coupon = make_coupon(kind=CouponType.PERCENT, value=Decimal("0.25"), minimum=Decimal("0.00"))
    assert coupon.discount(Decimal("80.00"), NOW_BEFORE) == Decimal("20.00")


@pytest.mark.parametrize(
    "fraction, expected",
    [(Decimal("1"), Decimal("100.00")), (Decimal("0.01"), Decimal("1.00"))],
)
def test_percent_upper_and_lower_bounds(fraction, expected):
    coupon = make_coupon(kind=CouponType.PERCENT, value=fraction, minimum=Decimal("0"))
    assert coupon.discount(Decimal("100.00"), NOW_BEFORE) == expected


def test_kind_branch_dispatch_differs_by_kind():
    fixed = make_coupon(kind=CouponType.FIXED, value=Decimal("0.5"))
    percent = make_coupon(kind=CouponType.PERCENT, value=Decimal("0.5"))
    assert fixed.discount(Decimal("100.00"), NOW_BEFORE) == Decimal("0.5")
    assert percent.discount(Decimal("100.00"), NOW_BEFORE) == Decimal("50.0")


def test_fixed_discount_may_exceed_subtotal():
    coupon = make_coupon(kind=CouponType.FIXED, value=Decimal("100.00"), minimum=Decimal("0"))
    assert coupon.discount(Decimal("10.00"), NOW_BEFORE) == Decimal("100.00")


# --- minimum spend boundary ------------------------------------------------------


@pytest.mark.parametrize(
    "coupon, expected",
    [
        (make_coupon(kind=CouponType.PERCENT, value=Decimal("0.10"), minimum=Decimal("50.00")), Decimal("5.00")),
        (make_coupon(kind=CouponType.FIXED, value=Decimal("5.00"), minimum=Decimal("50.00")), Decimal("5.00")),
    ],
)
def test_minimum_spend_is_inclusive(coupon, expected):
    assert coupon.discount(Decimal("50.00"), NOW_BEFORE) == expected


def test_subtotal_below_minimum_raises():
    coupon = make_coupon(kind=CouponType.FIXED, value=Decimal("5.00"), minimum=Decimal("50.00"))
    with pytest.raises(InvalidCouponError, match="minimum spend not met"):
        coupon.discount(Decimal("49.99"), NOW_BEFORE)


# --- expiry boundary -------------------------------------------------------------


def test_now_just_before_expiry_succeeds():
    coupon = make_coupon(value=Decimal("1.00"))
    now = datetime(2025, 1, 1, 11, 59, 59, tzinfo=timezone.utc)
    assert coupon.discount(Decimal("10.00"), now) == Decimal("1.00")


def test_now_equal_to_expiry_raises():
    coupon = make_coupon(value=Decimal("1.00"))
    with pytest.raises(InvalidCouponError, match="coupon expired"):
        coupon.discount(Decimal("10.00"), EXPIRES)


def test_now_after_expiry_raises():
    coupon = make_coupon(value=Decimal("1.00"))
    now = datetime(2025, 1, 1, 12, 0, 1, tzinfo=timezone.utc)
    with pytest.raises(InvalidCouponError, match="coupon expired"):
        coupon.discount(Decimal("10.00"), now)


# --- amount validation -----------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")],
)
def test_non_finite_value_rejected(value):
    coupon = make_coupon(kind=CouponType.FIXED, value=value)
    with pytest.raises(InvalidCouponError, match="invalid coupon amount"):
        coupon.discount(Decimal("10.00"), NOW_BEFORE)


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-1.00")])
def test_non_positive_value_rejected(value):
    coupon = make_coupon(kind=CouponType.FIXED, value=value)
    with pytest.raises(InvalidCouponError, match="invalid coupon amount"):
        coupon.discount(Decimal("10.00"), NOW_BEFORE)


@pytest.mark.parametrize(
    "coupon",
    [
        make_coupon(kind=CouponType.FIXED, value=1.0),
        make_coupon(kind=CouponType.FIXED, value=1),
        make_coupon(kind=CouponType.FIXED, value=Decimal("1.00"), minimum=0),
        make_coupon(kind=CouponType.FIXED, value=Decimal("1.00"), minimum=0.0),
    ],
)
def test_non_decimal_amounts_rejected(coupon):
    with pytest.raises(InvalidCouponError, match="invalid coupon amount"):
        coupon.discount(Decimal("10.00"), NOW_BEFORE)


def test_negative_minimum_rejected():
    coupon = make_coupon(kind=CouponType.FIXED, value=Decimal("1.00"), minimum=Decimal("-0.01"))
    with pytest.raises(InvalidCouponError, match="invalid coupon amount"):
        coupon.discount(Decimal("10.00"), NOW_BEFORE)


# --- percent overflow ------------------------------------------------------------


def test_percent_greater_than_one_rejected():
    coupon = make_coupon(kind=CouponType.PERCENT, value=Decimal("1.01"))
    with pytest.raises(InvalidCouponError, match="percentage exceeds one"):
        coupon.discount(Decimal("10.00"), NOW_BEFORE)


# --- kind validation -------------------------------------------------------------


def test_non_coupon_type_kind_rejected():
    coupon = make_coupon(kind=CouponType.FIXED, value=Decimal("1.00"))
    object.__setattr__(coupon, "kind", "fixed")
    with pytest.raises(InvalidCouponError, match="unknown coupon type"):
        coupon.discount(Decimal("10.00"), NOW_BEFORE)


# --- timezone awareness ----------------------------------------------------------


@pytest.mark.parametrize(
    "coupon, now",
    [
        (make_coupon(expires_at=datetime(2025, 1, 1, 12, 0)), NOW_BEFORE),
        (make_coupon(), datetime(2025, 1, 1, 10, 0)),
    ],
)
def test_naive_timestamps_rejected(coupon, now):
    with pytest.raises(InvalidCouponError, match="timezone-aware timestamps required"):
        coupon.discount(Decimal("10.00"), now)


@pytest.mark.parametrize(
    "coupon, now",
    [
        (make_coupon(expires_at=None), NOW_BEFORE),
        (make_coupon(), None),
    ],
)
def test_non_datetime_timestamps_rejected(coupon, now):
    with pytest.raises(InvalidCouponError, match="timezone-aware timestamps required"):
        coupon.discount(Decimal("10.00"), now)


# --- validation ordering ---------------------------------------------------------


def test_invalid_kind_wins_over_expiry():
    coupon = make_coupon(kind=CouponType.FIXED, value=Decimal("1.00"))
    object.__setattr__(coupon, "kind", "fixed")
    past = datetime(2025, 1, 1, 13, 0, tzinfo=timezone.utc)
    with pytest.raises(InvalidCouponError, match="unknown coupon type"):
        coupon.discount(Decimal("10.00"), past)


def test_bad_amount_wins_over_expiry():
    coupon = make_coupon(kind=CouponType.FIXED, value=Decimal("0"))
    past = datetime(2025, 1, 1, 13, 0, tzinfo=timezone.utc)
    with pytest.raises(InvalidCouponError, match="invalid coupon amount"):
        coupon.discount(Decimal("10.00"), past)
