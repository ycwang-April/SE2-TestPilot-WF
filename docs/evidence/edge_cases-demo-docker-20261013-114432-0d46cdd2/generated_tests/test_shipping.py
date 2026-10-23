from shipping import shipping_fe

def test_regular_small():
    assert shipping_fe(1) == 5
