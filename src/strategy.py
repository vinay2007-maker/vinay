"""Transparent EMA-crossover baseline; it makes no profitability claim."""
from enum import Enum
import pandas as pd
from .indicators import ema, rsi

class Signal(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"

def generate_signal(frame: pd.DataFrame, fast_period=20, slow_period=50, rsi_period=14) -> Signal:
    if len(frame) < slow_period + 1: return Signal.HOLD
    fast, slow = ema(frame["close"], fast_period), ema(frame["close"], slow_period)
    momentum = rsi(frame["close"], rsi_period)
    if any(pd.isna(x) for x in (fast.iloc[-2], fast.iloc[-1], slow.iloc[-2], slow.iloc[-1], momentum.iloc[-1])): return Signal.HOLD
    if fast.iloc[-2] <= slow.iloc[-2] and fast.iloc[-1] > slow.iloc[-1] and momentum.iloc[-1] >= 50: return Signal.LONG
    if fast.iloc[-2] >= slow.iloc[-2] and fast.iloc[-1] < slow.iloc[-1] and momentum.iloc[-1] <= 50: return Signal.SHORT
    return Signal.HOLD
