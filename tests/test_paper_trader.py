import pytest
from src.paper_trader import PaperTrader
from src.portfolio import Portfolio
from src.risk_manager import RiskManager
from src.strategy import Signal

def make():
    p=Portfolio(fee_rate=0); r=RiskManager(max_position_size=100); return PaperTrader(p,r),p,r

def test_long_take_profit_and_short_stop():
    t,p,r=make(); t.execute(r.create_plan(Signal.LONG,p.equity,100,90)); assert t.check_exit(0,120)=='TAKE_PROFIT'; assert p.realized_pnl==pytest.approx(200)
    t.execute(r.create_plan(Signal.SHORT,p.equity,100,110)); assert t.check_exit(0,110)=='STOP_LOSS'; assert p.realized_pnl==pytest.approx(100)

def test_kill_switch():
    t,p,r=make(); r.kill_switch=True
    with pytest.raises(ValueError): t.execute(r.create_plan(Signal.LONG,p.equity,100,90))
