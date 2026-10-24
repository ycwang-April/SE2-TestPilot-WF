"""Behavioral tests for models.Product, models.OrderLine and the value enums."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from errors import InvalidOrderError
from models import CouponType, CustomerLevel, OrderLine, Product


# --- Product: valid construction -------------------------------------------------


def test_product_valid_construction_preserves_fields_and_is_frozen():
    product = Product(sku="ABC-1", price=Decimal("9.99"))
    assert product.sku == "ABC-1"
    assert product.price == Decimal("9.99")
    with pytest.raises(FrozenInstanceError):
        product.sku = "OTHER"


def test_product_zero_price_is_allowed():
    product = Product(sku="A", price=Decimal("0"))
    assert product.price == Decimal("0")


# --- Product: invalid SKU -------------------------------------------------------


@pytest.mark.parametrize("sku", ["", "   ", None, 123])
def test_product_invalid_sku_rejected(sku):
    with pytest.raises(InvalidOrderError, match="SKU must be nonempty"):
        Product(sku=sku, price=Decimal("1.00"))


# --- Product: invalid price -----------------------------------------------------


@pytest.mark.parametrize(
    "price",
    [
        9.99,
        10,
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_product_invalid_price_rejected(price):
    with pytest.raises(InvalidOrderError, match="price must be a finite nonnegative Decimal"):
        Product(sku="A", price=price)


def test_product_negative_price_rejected():
    with pytest.raises(InvalidOrderError, match="price must be a finite nonnegative Decimal"):
        Product(sku="A", price=Decimal("-0.01"))


# --- OrderLine: valid construction ----------------------------------------------


def test_orderline_valid_construction_is_frozen():
    line = OrderLine(sku="A", quantity=3)
    assert line.sku == "A"
    assert line.quantity == 3
    with pytest.raises(FrozenInstanceError):
        line.sku = "B"


def test_orderline_quantity_one_is_minimum_allowed():
    line = OrderLine(sku="A", quantity=1)
    assert line.quantity == 1


# --- OrderLine: invalid quantity ------------------------------------------------


@pytest.mark.parametrize("quantity", [0, -1, -100])
def test_orderline_nonpositive_quantity_rejected(quantity):
    with pytest.raises(InvalidOrderError, match="quantity must be a positive integer"):
        OrderLine(sku="A", quantity=quantity)


@pytest.mark.parametrize("quantity", [True, False])
def test_orderline_bool_quantity_rejected(quantity):
    with pytest.raises(InvalidOrderError, match="quantity must be a positive integer"):
        OrderLine(sku="A", quantity=quantity)


@pytest.mark.parametrize("quantity", [1.0, Decimal("1"), "1", None])
def test_orderline_nonint_quantity_rejected(quantity):
    with pytest.raises(InvalidOrderError, match="quantity must be a positive integer"):
        OrderLine(sku="A", quantity=quantity)


# --- OrderLine: invalid SKU -----------------------------------------------------


@pytest.mark.parametrize("sku", ["", "   ", None])
def test_orderline_invalid_sku_rejected(sku):
    with pytest.raises(InvalidOrderError, match="SKU must be nonempty"):
        OrderLine(sku=sku, quantity=1)


def test_orderline_sku_check_precedes_quantity_check():
    with pytest.raises(InvalidOrderError, match="SKU must be nonempty"):
        OrderLine(sku="", quantity=0)


# --- enums ----------------------------------------------------------------------


def test_customer_level_resolves_by_value():
    assert CustomerLevel("regular") is CustomerLevel.REGULAR
    assert CustomerLevel("vip") is CustomerLevel.VIP
    assert CustomerLevel.REGULAR.value == "regular"
    assert CustomerLevel.VIP.value == "vip"


def test_coupon_type_resolves_by_value():
    assert CouponType("fixed") is CouponType.FIXED
    assert CouponType("percent") is CouponType.PERCENT
    assert CouponType.FIXED.value == "fixed"
    assert CouponType.PERCENT.value == "percent"


def test_enum_unknown_value_raises_value_error():
    with pytest.raises(ValueError):
        CustomerLevel("gold")
    with pytest.raises(ValueError):
        CouponType("unknown")


# --- dataclass value equality ----------------------------------------------------


def test_product_value_equality_and_hash():
    a = Product(sku="A", price=Decimal("1"))
    b = Product(sku="A", price=Decimal("1"))
    c = Product(sku="A", price=Decimal("2"))
    assert a == b
    assert hash(a) == hash(b)
    assert a != c


def test_orderline_value_equality_and_hash():
    a = OrderLine(sku="A", quantity=2)
    b = OrderLine(sku="A", quantity=2)
    c = OrderLine(sku="A", quantity=3)
    assert a == b
    assert hash(a) == hash(b)
    assert a != c
