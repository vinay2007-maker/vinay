import json

import pandas as pd

from src.delta_market_data import (
    Candle,
    CandleAccumulator,
    DeltaMarketData,
    REST_CANDLES_URL,
    WEBSOCKET_URL,
    normalize_timestamp,
    parse_candle_message,
)


def candle_message(timestamp, close=101):
    return {
        "type": "candlestick_1m",
        "symbol": "BTCUSD",
        "timestamp": timestamp,
        "open": 100,
        "high": max(100, close),
        "low": min(100, close),
        "close": close,
        "volume": 2,
    }


def test_parse_candle_message_accepts_public_candle_payload():
    candle = parse_candle_message(json.dumps(candle_message(1_700_000_000)))

    assert candle == Candle(1_700_000_000, 100, 101, 100, 101, 2)


def test_delta_candle_timestamp_is_microseconds_and_formats_as_utc():
    timestamp = 1_789_810_759_472_477
    candle = parse_candle_message({
        "close": 81280.0,
        "high": 81287.0,
        "low": 81257.5,
        "open": 81257.5,
        "timestamp": timestamp,
        "type": "candlestick_1m",
        "symbol": "BTCUSD",
        "resolution": "1m",
        "volume": 881.0,
        "candle_start_time": 1_789_810_740_000_000,
        "last_updated": timestamp,
        "sUID": "BTCUSD_#_BTCUSD_#_1",
    })

    assert normalize_timestamp(timestamp) == 1789810759.472477
    assert candle.timestamp == 1789810759.472477


def test_parse_candle_message_rejects_malformed_data():
    assert parse_candle_message({"type": "candlestick_1m", "close": 101}) is None
    assert parse_candle_message("not json") is None


def test_accumulator_emits_only_completed_candles_and_current_price():
    accumulator = CandleAccumulator()
    first = parse_candle_message(candle_message(1_700_000_000, 101))
    update = parse_candle_message(candle_message(1_700_000_000, 102))
    next_candle = parse_candle_message(candle_message(1_700_000_060, 103))

    assert accumulator.update(first) is None
    assert accumulator.update(update) is None
    completed, live_price = accumulator.update(next_candle)

    assert completed.close == 102
    assert live_price == 103


def test_history_loader_uses_public_rest_without_authentication():
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"success": True, "result": [candle_message(1_700_000_000)]}).encode()

    requests = []

    def fake_opener(request, timeout):
        requests.append((request.full_url, request.headers, timeout))
        return FakeResponse()

    market = DeltaMarketData(warmup_candles=1, opener=fake_opener)
    history = market.load_history(end=1_700_000_060)

    assert list(history["close"]) == [101]
    assert requests[0][0].startswith(REST_CANDLES_URL)
    assert "Authorization" not in requests[0][1]


def test_websocket_subscription_is_public_candlestick_only():
    class FakeSocket:
        def __init__(self):
            self.message = None

        def send(self, message):
            self.message = json.loads(message)

    socket = FakeSocket()
    DeltaMarketData(symbol="BTCUSD")._subscribe(socket)

    assert WEBSOCKET_URL.startswith("wss://")
    assert socket.message == {
        "type": "subscribe",
        "payload": {
            "channels": [{"name": "candlestick_1m", "symbols": ["BTCUSD"]}]
        },
    }
    assert "orders" not in json.dumps(socket.message).lower()
