"""Basic pandas indicators with NaN warm-up periods."""
import pandas as pd

def ema(close: pd.Series, period: int = 20) -> pd.Series:
    if period <= 0: raise ValueError("period must be positive")
    return close.astype(float).ewm(span=period, adjust=False, min_periods=period).mean()

def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    if period <= 0: raise ValueError("period must be positive")
    delta = close.astype(float).diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    result = 100 - (100 / (1 + gain / loss.replace(0, float("nan"))))
    result[(loss == 0) & (gain > 0)] = 100
    result[(loss == 0) & (gain == 0)] = 50
    return result

def atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    if period <= 0: raise ValueError("period must be positive")
    previous = frame["close"].shift(1)
    true_range = pd.concat([frame["high"] - frame["low"], (frame["high"] - previous).abs(), (frame["low"] - previous).abs()], axis=1).max(axis=1)
    return true_range.rolling(period, min_periods=period).mean()
