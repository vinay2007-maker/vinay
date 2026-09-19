import pandas as pd

from src.config import Settings
from src.live_signal import build_signal_report
from src.strategy import Signal


def candles():
    closes = list(range(100, 160))
    return pd.DataFrame({
        "timestamp": list(range(1_700_000_000, 1_700_000_060)),
        "open": closes,
        "high": [value + 1 for value in closes],
        "low": [value - 1 for value in closes],
        "close": closes,
        "volume": [1.0] * len(closes),
    })


def test_long_signal_report_is_explicitly_not_executed():
    settings = Settings(symbol="XAUTUSD")
    report = build_signal_report(
        candles(),
        160.5,
        settings,
        signal_fn=lambda frame: Signal.LONG,
        atr_fn=lambda frame, period: pd.Series([2.0]),
    )

    assert "DELTA LIVE — SIGNAL ONLY" in report
    assert "NO ORDERS WILL BE SENT" in report
    assert "Signal: LONG" in report
    assert "Proposed Entry: 160.50000000 (NOT EXECUTED)" in report
    assert "Stop Loss:       156.50000000" in report
    assert "Take Profit:     168.50000000" in report
    assert "Quantity:        1.00000000" in report
    assert "Risk Amount:     0.00400000" in report
    assert "Risk/Reward:     2.00" in report
    assert "STATUS: SIGNAL ONLY — NOT EXECUTED" in report


def test_hold_signal_report_has_no_trade_plan():
    report = build_signal_report(
        candles(),
        160.5,
        Settings(symbol="BTCUSD"),
        signal_fn=lambda frame: Signal.HOLD,
        atr_fn=lambda frame, period: pd.Series([2.0]),
    )

    assert "Signal: HOLD" in report
    assert "PROPOSED ENTRY" not in report
    assert "Waiting for confirmed setup..." in report
    assert "NO ORDERS WILL BE SENT" in report


def test_short_signal_report_contains_proposed_plan_fields():
    report = build_signal_report(
        candles(),
        160.5,
        Settings(symbol="XAUTUSD"),
        signal_fn=lambda frame: Signal.SHORT,
        atr_fn=lambda frame, period: pd.Series([2.0]),
    )

    assert "Symbol: XAUTUSD" in report
    assert "Signal: SHORT" in report
    assert "Proposed Entry: 160.50000000 (NOT EXECUTED)" in report
    assert "Stop Loss:       164.50000000" in report
    assert "Take Profit:     152.50000000" in report
    assert "Quantity:        1.00000000" in report
    assert "Risk Amount:     0.00400000" in report
    assert "Risk/Reward:     2.00" in report


def test_signal_report_does_not_call_order_functions(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("order function must not be called")

    monkeypatch.setattr("src.paper_trader.PaperTrader.execute", fail_if_called)

    report = build_signal_report(
        candles(),
        160.5,
        Settings(symbol="XAUTUSD"),
        signal_fn=lambda frame: Signal.LONG,
        atr_fn=lambda frame, period: pd.Series([2.0]),
    )

    assert "STATUS: SIGNAL ONLY — NOT EXECUTED" in report


def test_live_signal_report_formats_timestamp_as_utc():
    frame = candles()
    frame["timestamp"] = frame["timestamp"].astype(float)
    frame.loc[frame.index[-1], "timestamp"] = 1789810759.472477

    report = build_signal_report(
        frame,
        160.5,
        Settings(symbol="XAUTUSD"),
        signal_fn=lambda frame: Signal.HOLD,
    )

    assert "Completed candle: 2026-09-19T09:39:19.472477+00:00" in report
