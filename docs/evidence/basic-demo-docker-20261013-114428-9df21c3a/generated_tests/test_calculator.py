import pytest
from calculator import divide, clamp

def test_divide():
    assert divide(6, 3) == 2
    assert divide(0, 3) == 0
    assert divide(-6, 3) == -2
    with pytest.raises(ValueError, match="zero"):
        divide(1, 0)
    with pytest.raises(TypeError):
        divide("bad", 2)

@pytest.mark.parametrize("value,expected", [(-1, 0), (0, 0), (3, 3), (5, 5), (6, 5)])
def test_clamp(value, expected):
    assert clamp(value, 0, 5) == expected

def test_invalid_bounds():
    with pytest.raises(ValueError, match="lower"):
        clamp(1, 5, 0)
