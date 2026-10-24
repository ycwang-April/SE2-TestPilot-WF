import pytest

from shipping import shipping_fee


@pytest.mark.parametrize("weight", [0, -1, -0.5])
@pytest.mark.parametrize("express", [False, True])
def test_nonpositive_weight_raises_value_error(weight, express):
    with pytest.raises(ValueError, match="weight must be positive"):
        shipping_fee(weight, express=express)


@pytest.mark.parametrize(
    "weight, expected",
    [
        (1, 5),
        (1.0001, 10),
    ],
)
def test_tier1_upper_boundary(weight, expected):
    assert shipping_fee(weight) == expected


@pytest.mark.parametrize(
    "weight, expected",
    [
        (5, 10),
        (5.0001, 20),
    ],
)
def test_tier2_upper_boundary(weight, expected):
    assert shipping_fee(weight) == expected


@pytest.mark.parametrize(
    "weight, expected",
    [
        (0.5, 5),
        (2, 10),
        (10, 20),
    ],
)
def test_base_tier_interior(weight, expected):
    assert shipping_fee(weight, express=False) == expected


@pytest.mark.parametrize(
    "weight, expected",
    [
        (0.5, 13),
        (2, 18),
        (10, 28),
    ],
)
def test_express_adds_eight(weight, expected):
    assert shipping_fee(weight, express=True) == expected


@pytest.mark.parametrize(
    "weight, expected",
    [
        (1, 13),
        (5, 18),
    ],
)
def test_express_preserves_tier(weight, expected):
    assert shipping_fee(weight, express=True) == expected


def test_default_express_is_false():
    assert shipping_fee(2) == 10
