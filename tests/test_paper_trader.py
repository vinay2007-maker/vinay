import pytest
from src.paper_trader import PaperTrader
from src.portfolio import Portfolio
from src.risk_manager import RiskManager
from src.strategy import Signal

def make():
    p=Portfolio(fee_rate=0); r=RiskManager(max_position_size=100); return PaperTrader(p,r),p,r

def test_long_take_profit_and_short_stop():
    t,p,r=make(); t.execute(r.create_plan(Signal.LONG,p.equity,100,90)); assert t.check_exit(0,120)=='TAKE_PROFIT'; assert p.realized_pnl==pytest.approx(200)
    t.execute(r.create_plan(Signal.SHORT,p.equity,100,110)); assert t.check_exit(0,110)=='STOP_LOSS'; assert p.realized_pnl==pytest.approx(98)

def test_kill_switch():
    t,p,r=make(); r.kill_switch=True
    with pytest.raises(ValueError): t.execute(r.create_plan(Signal.LONG,p.equity,100,90))

def test_kill_switch_blocks_preapproved_plan_without_opening_position():
    t,p,r=make()
    plan = r.create_plan(Signal.LONG,p.equity,100,90)
    r.kill_switch = True

    with pytest.raises(ValueError, match="kill switch enabled"):
        t.execute(plan)

    assert p.positions == []

def test_long_stop_and_short_take_profit_exits():
    t,p,r=make()
    t.execute(r.create_plan(Signal.LONG,p.equity,100,90))
    assert t.check_exit(0,90) == 'STOP_LOSS'

    t.execute(r.create_plan(Signal.SHORT,p.equity,100,110))
    assert t.check_exit(0,80) == 'TAKE_PROFIT'
