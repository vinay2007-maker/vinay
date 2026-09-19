"""Deterministic data and validated historical OHLCV CSV loading."""
from dataclasses import dataclass
from pathlib import Path
import pandas as pd

REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}


def validate_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - {str(c).lower() for c in frame.columns}
    if missing:
        raise ValueError(f"OHLCV data is missing columns: {sorted(missing)}")
    result = frame.rename(columns={c: str(c).lower() for c in frame.columns}).copy()
    for column in REQUIRED_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="raise")
    if result.empty or result[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("OHLCV data must be non-empty and contain no nulls")
    if (result[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("OHLC prices must be positive")
    if (result["high"] < result[["open", "close"]].max(axis=1)).any() or (result["low"] > result[["open", "close"]].min(axis=1)).any():
        raise ValueError("OHLC high/low values are inconsistent")
    return result.reset_index(drop=True)

@dataclass
class SimulatedMarketData:
    candles: pd.DataFrame

    def __post_init__(self):
        self.candles = validate_ohlcv(self.candles)

    @classmethod
    def from_closes(cls, closes: list[float], volume: float = 1.0):
        if not closes:
            raise ValueError("At least one close is required")
        close = pd.Series(closes, dtype=float)
        frame = pd.DataFrame({"open": close.shift(1).fillna(close), "close": close, "volume": volume})
        frame["high"] = frame[["open", "close"]].max(axis=1)
        frame["low"] = frame[["open", "close"]].min(axis=1)
        return cls(frame)

    def latest(self):
        return self.candles.iloc[-1].to_dict()

def load_ohlcv_csv(path: str | Path) -> pd.DataFrame:
    return validate_ohlcv(pd.read_csv(path))
