import pytest
from src.portfolio import Portfolio

def test_long_and_short_pnl():
    p=Portfolio(fee_rate=0); p.open_position('LONG',100,2,90,120); assert p.close_position(0,110)==pytest.approx(20)
    p.open_position('SHORT',100,2,110,80); assert p.close_position(0,90)==pytest.approx(20)

def test_fees():
    p=Portfolio(1000,.001); p.open_position('LONG',100,2,90,120); p.close_position(0,110)
    assert p.fees==pytest.approx(.42); assert p.realized_pnl==pytest.approx(19.58)

def test_unrealized_and_equity():
    p=Portfolio(fee_rate=0); p.open_position('LONG',100,2,90,120); assert p.unrealized_pnl({0:105})==pytest.approx(10); assert p.equity==pytest.approx(10000)
