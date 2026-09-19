import pytest
from src.risk_manager import RiskManager
from src.strategy import Signal

def test_one_percent_sizing():
    p = RiskManager(max_position_size=100).create_plan(Signal.LONG, 10000, 100, 90)
    assert p.quantity == pytest.approx(10); assert p.risk_amount == pytest.approx(100)

def test_max_position_cap():
    p = RiskManager(max_position_size=1).create_plan(Signal.LONG, 10000, 100, 1)
    assert p.quantity == 1; assert p.risk_amount == 99

def test_limits_and_invalid_plan():
    r = RiskManager()
    with pytest.raises(ValueError): r.create_plan(Signal.LONG, 10000, 100, 100)
    with pytest.raises(ValueError): r.create_plan(Signal.LONG, 10000, 100, 90, daily_loss=300)
    with pytest.raises(ValueError): r.create_plan(Signal.LONG, 10000, 100, 90, open_positions=2)
    with pytest.raises(ValueError): r.create_plan(Signal.LONG, 10000, 100, 90, take_profit=105)
