"""Behavioral tests for the errors module exception hierarchy."""

import pytest

from errors import (
    InvalidCouponError,
    InvalidOrderError,
    OrderError,
    OutOfStockError,
)


SUBCLASSES = [InvalidOrderError, OutOfStockError, InvalidCouponError]


# --- base class contract ---------------------------------------------------------


def test_order_error_is_value_error_subclass():
    assert issubclass(OrderError, ValueError)


def test_order_error_raise_and_catch_as_value_error():
    with pytest.raises(ValueError) as excinfo:
        raise OrderError("boom")
    assert isinstance(excinfo.value, OrderError)
    assert str(excinfo.value) == "boom"


# --- subclass relationships ------------------------------------------------------


@pytest.mark.parametrize("exc_cls", SUBCLASSES)
def test_subclasses_derive_from_order_error(exc_cls):
    assert issubclass(exc_cls, OrderError)
    assert issubclass(exc_cls, ValueError)


@pytest.mark.parametrize("exc_cls", SUBCLASSES)
def test_subclass_instance_caught_as_order_error_and_value_error(exc_cls):
    with pytest.raises(OrderError) as order_excinfo:
        raise exc_cls("msg")
    assert isinstance(order_excinfo.value, exc_cls)
    assert str(order_excinfo.value) == "msg"

    with pytest.raises(ValueError) as vc_excinfo:
        raise exc_cls("msg")
    assert isinstance(vc_excinfo.value, exc_cls)
    assert str(vc_excinfo.value) == "msg"


# --- sibling distinctness --------------------------------------------------------


def test_invalid_coupon_error_not_caught_by_out_of_stock_handler():
    with pytest.raises(InvalidCouponError):
        try:
            raise InvalidCouponError("cpn")
        except OutOfStockError:
            pytest.fail("OutOfStockError handler must not catch InvalidCouponError")


def test_invalid_order_error_not_caught_by_out_of_stock_handler():
    with pytest.raises(InvalidOrderError):
        try:
            raise InvalidOrderError("inv")
        except OutOfStockError:
            pytest.fail("OutOfStockError handler must not catch InvalidOrderError")


def test_out_of_stock_error_not_caught_by_invalid_coupon_handler():
    with pytest.raises(OutOfStockError):
        try:
            raise OutOfStockError("oos")
        except InvalidCouponError:
            pytest.fail("InvalidCouponError handler must not catch OutOfStockError")


# --- class identity --------------------------------------------------------------


def test_exception_classes_are_distinct_types():
    classes = [OrderError, InvalidOrderError, OutOfStockError, InvalidCouponError]
    assert len({id(cls) for cls in classes}) == len(classes)
    assert InvalidOrderError is not OrderError
    assert OutOfStockError is not OrderError
    assert InvalidCouponError is not OrderError
    assert InvalidOrderError is not OutOfStockError
    assert InvalidOrderError is not InvalidCouponError
    assert OutOfStockError is not InvalidCouponError
