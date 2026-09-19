import json

import pandas as pd
import pytest

import src.historical_backtest as historical
from src.backtester import BacktestResult, TradeReport
from src.market_data import validate_ohlcv


def candle_row(timestamp=1_700_000_000, close=100.0):
    return {
        "time": timestamp,
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": 10,
    }


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_historical_rows_parse_and_validate_ohlcv():
    frame = historical.parse_historical_rows({
        "success": True,
        "result": [candle_row(1_700_000_060, 101), candle_row(1_700_000_000, 100)],
    })

    assert list(frame["timestamp"]) == [1_700_000_000, 1_700_000_060]
    assert list(frame["close"]) == [100, 101]
    pd.testing.assert_frame_equal(frame, validate_ohlcv(frame))


def test_download_uses_configurable_period_and_resolution_without_authentication():
    requests = []

    def opener(request, timeout):
        requests.append(request)
        return FakeResponse({"success": True, "result": [candle_row()]})

    frame = historical.download_historical_candles(
        "XAUTUSD", "2026-01-01T00:00:00Z", "2026-01-01T00:05:00Z",
        resolution="1m", opener=opener,
    )

    assert len(frame) == 1
    assert requests[0].full_url.startswith(historical.REST_CANDLES_URL)
    assert "symbol=XAUTUSD" in requests[0].full_url
    assert "resolution=1m" in requests[0].full_url
    assert "Authorization" not in requests[0].headers
    assert "order" not in requests[0].full_url.lower()


def test_download_rejects_oversized_range_before_request():
    with pytest.raises(ValueError, match="max_candles"):
        historical.download_historical_candles(
            "XAUTUSD", 1_700_000_000, 1_700_000_000 + 60 * 11,
            max_candles=10, opener=lambda *args: pytest.fail("request made"),
        )


def test_save_and_load_csv_round_trip(tmp_path):
    frame = historical.parse_historical_rows({"result": [candle_row()]})
    path = historical.save_candles(frame, tmp_path / "xautusd.csv")

    loaded = historical.load_candles(path)

    pd.testing.assert_frame_equal(loaded, frame)


def test_load_csv_rejects_invalid_ohlcv(tmp_path):
    path = tmp_path / "invalid.csv"
    pd.DataFrame([{"open": 100, "high": 99, "low": 100, "close": 100, "volume": 1}]).to_csv(path, index=False)

    with pytest.raises(ValueError, match="OHLC high/low"):
        historical.load_candles(path)


def test_api_failure_includes_public_response_and_does_not_fallback():
    def opener(request, timeout):
        return FakeResponse({"success": False, "error": {"code": "PRODUCT_NOT_FOUND", "message": "unknown symbol"}})

    with pytest.raises(historical.HistoricalDataError, match="PRODUCT_NOT_FOUND"):
        historical.download_historical_candles(
            "XAUTUSD", 1_700_000_000, 1_700_000_060, opener=opener,
        )


def test_backtest_integration_uses_downloaded_validated_data(monkeypatch):
    rows = [candle_row(1_700_000_000 + index * 60, 100 + index) for index in range(60)]

    monkeypatch.setattr(
        historical,
        "download_historical_candles",
        lambda *args, **kwargs: historical.parse_historical_rows({"result": rows}),
    )
    result = historical.run_historical_backtest(
        "XAUTUSD", 1_700_000_000, 1_700_003_600, csv_path=None,
    )[1]

    assert isinstance(result, BacktestResult)
    assert result.final_balance == pytest.approx(10_000)


def test_only_public_history_endpoint_is_defined_for_downloader():
    assert historical.REST_CANDLES_URL.endswith("/v2/history/candles")
    assert "private" not in historical.REST_CANDLES_URL
    assert "order" not in historical.REST_CANDLES_URL.lower()
    assert "api_key" not in historical.REST_CANDLES_URL.lower()


def test_trade_report_formats_long_short_reasons_and_accounting():
    frame = historical.parse_historical_rows({"result": [candle_row()]})
    result = BacktestResult(
        2, 1, 1, .5, 5, .3, .2, .5, 4.5, 2, 10004.5,
        trades=[
            TradeReport(1, "LONG", 1_700_000_000, 100, 1_700_000_060, 110, 90, 120, 2, 20, .2, .22, .42, 19.58, "TAKE_PROFIT"),
            TradeReport(2, "SHORT", 1_700_000_060, 110, 1_700_000_120, 120, 120, 80, 2, -20, .22, .24, .46, -20.46, "STOP_LOSS"),
        ],
    )

    report = historical.format_backtest_report(result, frame, "XAUTUSD", "1m", include_trades=True)

    assert "LONG trades: 1" in report
    assert "SHORT trades: 1" in report
    assert "STOP LOSS exits: 1" in report
    assert "TAKE PROFIT exits: 1" in report
    assert "TRADE REPORT" in report
    assert "1 | LONG |" in report and "TAKE_PROFIT" in report
    assert "2 | SHORT |" in report and "STOP_LOSS" in report
    assert "0.42000000" in report
    assert "0.46000000" in report


def test_trades_option_only_adds_detail_without_changing_backtest_result(monkeypatch):
    frame = historical.parse_historical_rows({"result": [candle_row()]})
    result = BacktestResult(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10000)
    monkeypatch.setattr(historical, "download_historical_candles", lambda *args, **kwargs: frame)
    monkeypatch.setattr(historical, "run_backtest", lambda *args, **kwargs: result)

    default = historical.run_historical_backtest("XAUTUSD", 1, 2, csv_path=None)
    detailed = historical.run_historical_backtest("XAUTUSD", 1, 2, csv_path=None, include_trades=True)

    assert default[1] == detailed[1]
    assert "TRADE REPORT" not in default[2]
    assert "TRADE REPORT" in detailed[2]


def test_backtest_report_displays_selected_fee_model():
    frame = historical.parse_historical_rows({"result": [candle_row()]})
    result = BacktestResult(
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10000,
        entry_fee_type="maker", exit_fee_type="taker",
        maker_fee_rate=.0001, taker_fee_rate=.0005,
    )

    report = historical.format_backtest_report(result, frame, "XAUTUSD", "1m")

    assert "Fee model:" in report
    assert "Entry: MAKER 0.0001" in report
    assert "Exit: TAKER 0.0005" in report
