"""Read-only Delta Exchange public market-data adapter."""
from dataclasses import dataclass
import json
import logging
import math
import time
from typing import Any, Callable, Iterator
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .market_data import validate_ohlcv

LOGGER = logging.getLogger(__name__)
REST_CANDLES_URL = "https://api.india.delta.exchange/v2/history/candles"
WEBSOCKET_URL = "wss://socket.india.delta.exchange"


def normalize_timestamp(timestamp: Any) -> float | None:
    try:
        normalized = float(timestamp)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(normalized) or normalized <= 0:
        return None
    while normalized >= 100_000_000_000:
        normalized /= 1000
    if normalized >= 4_102_444_800:
        return None
    return normalized


@dataclass(frozen=True)
class Candle:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float

    def as_dict(self):
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


def parse_candle_message(message: Any) -> Candle | None:
    """Parse one public REST/WebSocket candle, returning None if malformed."""
    if isinstance(message, str):
        try:
            message = json.loads(message)
        except json.JSONDecodeError:
            return None
    if not isinstance(message, dict):
        return None

    candidate = message
    for key in ("candle", "data", "result"):
        nested = candidate.get(key)
        if isinstance(nested, dict):
            candidate = nested
            break

    timestamp = candidate.get(
        "candle_start_time",
        candidate.get("timestamp", candidate.get("time", candidate.get("start"))),
    )
    values = {name: candidate.get(name) for name in ("open", "high", "low", "close", "volume")}
    if timestamp is None or any(value is None for value in values.values()):
        return None
    try:
        timestamp = normalize_timestamp(timestamp)
        if timestamp is None:
            return None
        values = {name: float(value) for name, value in values.items()}
    except (TypeError, ValueError):
        return None

    frame = pd.DataFrame([{"timestamp": timestamp, **values}])
    try:
        validate_ohlcv(frame)
    except (TypeError, ValueError):
        return None
    return Candle(timestamp=timestamp, **values)


class CandleAccumulator:
    """Turn mutable candle updates into completed candles."""

    def __init__(self):
        self.current: Candle | None = None

    def update(self, candle: Candle) -> tuple[Candle, float] | None:
        if self.current is None:
            self.current = candle
            return None
        if candle.timestamp == self.current.timestamp:
            self.current = candle
            return None
        if candle.timestamp < self.current.timestamp:
            return None

        completed = self.current
        self.current = candle
        return completed, candle.close


class DeltaMarketData:
    """Unauthenticated public candles only; no private or order endpoints exist."""

    def __init__(
        self,
        symbol: str = "BTCUSD",
        resolution: str = "1m",
        warmup_candles: int = 200,
        timeout: float = 15.0,
        reconnect_delay: float = 2.0,
        opener: Callable[..., Any] = urlopen,
        websocket_factory: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.symbol = symbol
        self.resolution = resolution
        self.warmup_candles = warmup_candles
        self.timeout = timeout
        self.reconnect_delay = reconnect_delay
        self.opener = opener
        self.websocket_factory = websocket_factory
        self.sleep = sleep

    def load_history(self, end: int | None = None) -> pd.DataFrame:
        end = int(time.time()) if end is None else int(end)
        start = end - self.warmup_candles * 60
        query = urlencode({"resolution": self.resolution, "symbol": self.symbol, "start": start, "end": end})
        request = Request(f"{REST_CANDLES_URL}?{query}", headers={"Accept": "application/json"})
        with self.opener(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        rows = payload.get("result", []) if isinstance(payload, dict) else []
        candles = [parse_candle_message(row) for row in rows]
        candles = [candle for candle in candles if candle is not None]
        if not candles:
            raise ValueError("Delta returned no valid historical candles")
        frame = pd.DataFrame([candle.as_dict() for candle in candles])
        frame = frame.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
        return validate_ohlcv(frame)

    def _connect(self):
        factory = self.websocket_factory
        if factory is None:
            import websocket
            factory = websocket.create_connection
        return factory(WEBSOCKET_URL, timeout=self.timeout)

    def _subscribe(self, socket):
        socket.send(json.dumps({
            "type": "subscribe",
            "payload": {
                "channels": [{"name": "candlestick_1m", "symbols": [self.symbol]}]
            },
        }))

    def stream_completed_candles(self) -> Iterator[tuple[pd.DataFrame, float]]:
        history = self.load_history()
        accumulator = CandleAccumulator()
        while True:
            socket = None
            try:
                socket = self._connect()
                self._subscribe(socket)
                while True:
                    raw_message = socket.recv()
                    if isinstance(raw_message, str):
                        try:
                            decoded_message = json.loads(raw_message)
                        except json.JSONDecodeError:
                            LOGGER.warning("Ignoring malformed Delta candle message")
                            continue
                    else:
                        decoded_message = raw_message
                    if isinstance(decoded_message, dict) and decoded_message.get("type") not in (None, "candlestick_1m"):
                        continue
                    candle = parse_candle_message(decoded_message)
                    if candle is None:
                        LOGGER.warning("Ignoring malformed Delta candle message")
                        continue
                    completed = accumulator.update(candle)
                    if completed is None:
                        continue
                    completed_candle, live_price = completed
                    history = pd.concat(
                        [history, pd.DataFrame([completed_candle.as_dict()])],
                        ignore_index=True,
                    ).drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)
                    history = validate_ohlcv(history)
                    yield history, live_price
            except KeyboardInterrupt:
                raise
            except Exception as error:
                LOGGER.warning("Delta market-data connection lost: %s", error)
                self.sleep(self.reconnect_delay)
            finally:
                if socket is not None:
                    try:
                        socket.close()
                    except Exception:
                        pass
