"""Signal-only live display using Delta public market data."""
from datetime import datetime, timezone

import pandas as pd

from .config import Settings
from .delta_market_data import DeltaMarketData, normalize_timestamp
from .indicators import atr
from .market_data import validate_ohlcv
from .portfolio import Portfolio
from .risk_manager import RiskManager
from .strategy import Signal, generate_signal


def build_signal_report(candles, live_price, settings=None, signal_fn=generate_signal, atr_fn=atr):
    settings = settings or Settings.from_env()
    candles = validate_ohlcv(candles)
    latest = candles.iloc[-1]
    signal = signal_fn(candles)
    timestamp = latest.get("timestamp", "unknown")
    if timestamp != "unknown":
        timestamp = datetime.fromtimestamp(normalize_timestamp(timestamp), timezone.utc).isoformat()

    lines = [
        "----------------------------------------",
        "DELTA LIVE — SIGNAL ONLY",
        "NO ORDERS WILL BE SENT",
        "----------------------------------------",
        f"Symbol: {settings.symbol}",
        f"Time: {timestamp}",
        f"Live price: {float(live_price):.8f}",
        f"Signal: {signal.value}",
    ]
    if signal == Signal.HOLD:
        lines.append("----------------------------------------")
        return "\n".join(lines)

    volatility = atr_fn(candles, 14).iloc[-1]
    if pd.isna(volatility) or volatility <= 0:
        lines.extend([
            "STATUS: SIGNAL ONLY — PLAN UNAVAILABLE",
            "----------------------------------------",
        ])
        return "\n".join(lines)

    entry = float(live_price)
    stop = entry - settings.atr_multiplier * volatility if signal == Signal.LONG else entry + settings.atr_multiplier * volatility
    risk = RiskManager(
        settings.risk_per_trade,
        settings.max_daily_loss,
        settings.max_position_size,
        settings.max_open_positions,
        settings.risk_reward_ratio,
    )
    portfolio = Portfolio(settings.initial_balance, settings.fee_rate)
    plan = risk.create_plan(signal, portfolio.equity, entry, stop)
    lines.extend([
        f"PROPOSED ENTRY — NOT EXECUTED: {plan.entry:.8f}",
        f"STOP LOSS:       {plan.stop_loss:.8f}",
        f"TAKE PROFIT:     {plan.take_profit:.8f}",
        f"QUANTITY:        {plan.quantity:.8f}",
        "STATUS: SIGNAL ONLY — NOT EXECUTED",
        "----------------------------------------",
    ])
    return "\n".join(lines)


def run_live_signal():
    settings = Settings.from_env()
    market = DeltaMarketData(symbol=settings.symbol)
    for candles, live_price in market.stream_completed_candles():
        print(build_signal_report(candles, live_price, settings))


if __name__ == "__main__":
    run_live_signal()
