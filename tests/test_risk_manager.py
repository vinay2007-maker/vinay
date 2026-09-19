import pytest
from src.risk_manager import RiskManager
from src.strategy import Signal

def test_one_percent_sizing():
    p = RiskManager(max_position_size=100).create_plan(Signal.LONG, 10000, 100, 90)
    assert p.quantity == pytest.approx(100); assert p.risk_amount == pytest.approx(1)

def test_max_position_cap():
    p = RiskManager(max_position_size=1).create_plan(Signal.LONG, 10000, 100, 1)
    assert p.quantity == 1; assert p.risk_amount == pytest.approx(.099)

def test_limits_and_invalid_plan():
    r = RiskManager()
    with pytest.raises(ValueError): r.create_plan(Signal.LONG, 10000, 100, 100)
    with pytest.raises(ValueError): r.create_plan(Signal.LONG, 10000, 100, 90, daily_loss=300)
    with pytest.raises(ValueError): r.create_plan(Signal.LONG, 10000, 100, 90, open_positions=2)
    with pytest.raises(ValueError): r.create_plan(Signal.LONG, 10000, 100, 90, take_profit=105)

def test_short_plan_requires_stop_above_entry_and_target_below_entry():
    r = RiskManager()
    with pytest.raises(ValueError): r.create_plan(Signal.SHORT, 10000, 100, 90)
    with pytest.raises(ValueError): r.create_plan(Signal.SHORT, 10000, 100, 110, take_profit=105)

def test_risk_manager_returns_integer_contract_quantity():
    plan = RiskManager(max_position_size=20_000).create_plan(Signal.LONG, 10_000, 4800, 4790)

    assert plan.quantity == 10_000
    assert isinstance(plan.quantity, int)
    assert plan.risk_amount == pytest.approx(100)
