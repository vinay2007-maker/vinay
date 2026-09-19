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
    assert result.gross_pnl == pytest.approx(4.0)
    assert result.entry_fees == pytest.approx(.05)
    assert result.exit_fees == pytest.approx(.052)
    assert result.total_fees == pytest.approx(.102)
    assert result.net_pnl == pytest.approx(3.898)
    assert result.final_balance == pytest.approx(10003.898)

def test_backtest_drawdown_uses_marked_equity(monkeypatch):
    data = pd.DataFrame({
        'open': [100, 100, 99, 100], 'high': [100, 100, 99, 100],
        'low': [100, 100, 99, 100], 'close': [100, 100, 99, 100],
        'volume': [1, 1, 1, 1],
    })
    signals = iter([Signal.LONG, Signal.HOLD, Signal.HOLD])
    monkeypatch.setattr(backtester, 'generate_signal', lambda window: next(signals))
    monkeypatch.setattr(backtester, 'atr', lambda window, period: pd.Series([1.0] * len(window)))

    result = backtester.run_backtest(data, initial_balance=10_000, fee_rate=0)

    assert result.maximum_drawdown == pytest.approx(1.0)

def test_backtest_signal_windows_do_not_include_future_candles(monkeypatch):
    data = pd.DataFrame({
        'open': [100, 101, 102], 'high': [100, 101, 102],
        'low': [100, 101, 102], 'close': [100, 101, 102],
        'volume': [1, 1, 1],
    })
    seen_windows = []

    def signal_for_current_window(window):
        seen_windows.append(window['close'].tolist())
        return Signal.HOLD

    monkeypatch.setattr(backtester, 'generate_signal', signal_for_current_window)

    backtester.run_backtest(data, initial_balance=10_000, fee_rate=0)

    assert seen_windows == [[100], [100, 101]]

def test_signal_executes_at_next_candle_open_not_signal_close(monkeypatch):
    data = pd.DataFrame({
        'open': [100, 200, 300], 'high': [110, 220, 330],
        'low': [100, 200, 300], 'close': [110, 220, 330],
        'volume': [1, 1, 1],
    })
    signals = iter([Signal.LONG, Signal.HOLD])
    entries = []
    original_execute = backtester.PaperTrader.execute

    def capture_entry(trader, plan):
        entries.append(plan.entry)
        return original_execute(trader, plan)

    monkeypatch.setattr(backtester, 'generate_signal', lambda window: next(signals))
    monkeypatch.setattr(backtester, 'atr', lambda window, period: pd.Series([1.0] * len(window)))
    monkeypatch.setattr(backtester.PaperTrader, 'execute', capture_entry)

    backtester.run_backtest(data, initial_balance=10_000, fee_rate=0)

    assert entries == [200]
