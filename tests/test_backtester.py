import pandas as pd
import pytest
import src.backtester as backtester
from src.strategy import Signal


def test_backtest_reports_gross_fees_and_net(monkeypatch):
    data = pd.DataFrame({
        'open': [100, 100, 110], 'high': [100, 100, 110],
        'low': [100, 100, 110], 'close': [100, 100, 110],
        'volume': [1, 1, 1],
    })
    signals = iter([Signal.LONG, Signal.HOLD])
    monkeypatch.setattr(backtester, 'generate_signal', lambda window: next(signals))
    monkeypatch.setattr(backtester, 'atr', lambda window, period: pd.Series([1.0] * len(window)))

    result = backtester.run_backtest(data, initial_balance=10_000, fee_rate=.0005)
    assert result.total_trades == 1
    assert result.gross_pnl == pytest.approx(10.0)
    assert result.entry_fees == pytest.approx(.05)
    assert result.exit_fees == pytest.approx(.055)
    assert result.total_fees == pytest.approx(.105)
    assert result.net_pnl == pytest.approx(9.895)
    assert result.final_balance == pytest.approx(10009.895)
