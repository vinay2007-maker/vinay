import pytest
from src.portfolio import Portfolio


def test_long_and_short_pnl():
    p = Portfolio(fee_rate=0)
    p.open_position('LONG', 100, 2, 90, 120)
    assert p.close_position(0, 110) == pytest.approx(.02)
    p.open_position('SHORT', 100, 2, 110, 80)
    assert p.close_position(0, 90) == pytest.approx(.02)


def test_fees():
    p = Portfolio(1000, .001)
    p.open_position('LONG', 100, 2, 90, 120)
    p.close_position(0, 110)
    assert p.entry_fees == pytest.approx(.0002)
    assert p.exit_fees == pytest.approx(.00022)
    assert p.fees == pytest.approx(.00042)
    assert p.gross_realized_pnl == pytest.approx(.02)
    assert p.realized_pnl == pytest.approx(.01958)


def test_unrealized_and_equity_positive_and_negative():
    p = Portfolio(fee_rate=0)
    p.open_position('LONG', 100, 2, 90, 120)
    assert p.unrealized_pnl({0: 105}) == pytest.approx(.01)
    assert p.equity == pytest.approx(10000)
    assert p.unrealized_pnl({0: 95}) == pytest.approx(-.01)
    assert p.equity == pytest.approx(10000)

def test_marked_equity_includes_unrealized_pnl():
    p = Portfolio(fee_rate=0)
    p.open_position('LONG', 100, 2, 90, 120)

    assert p.equity_at({0: 105}) == pytest.approx(10000.01)
    assert p.equity_at({0: 95}) == pytest.approx(9999.99)

def test_final_balance_reconciles_to_net_realized_pnl():
    p = Portfolio(1000, .001)
    p.open_position('LONG', 100, 2, 90, 120)
    p.close_position(0, 110)

    assert p.realized_pnl == pytest.approx(p.gross_realized_pnl - p.fees)
    assert p.balance == pytest.approx(p.initial_balance + p.realized_pnl)

def test_fee_formula_uses_base_unit_notional_for_xautusd_assumption():
    p = Portfolio(initial_balance=10_000, fee_rate=.0005)
    p.open_position('LONG', 4377.88, 1, 4370, 4390)
    p.close_position(0, 4377.88)

    assert p.notional_for(4800, 1) == pytest.approx(4.80)
    assert p.entry_fees == pytest.approx(4377.88 * 1 * .001 * .0005)
    assert p.exit_fees == pytest.approx(4377.88 * 1 * .001 * .0005)
