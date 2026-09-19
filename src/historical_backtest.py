"""Public historical market-data download and paper backtest CLI."""
from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import time
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .backtester import BacktestResult, TradeReport, run_backtest
from .config import Settings
from .delta_market_data import REST_CANDLES_URL, parse_candle_message
from .market_data import validate_ohlcv

RESOLUTION_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "1d": 86400,
    "1w": 604800,
}
DEFAULT_MAX_CANDLES = 10_000


class HistoricalDataError(RuntimeError):
    """Raised when public historical data cannot be downloaded or validated."""


def parse_period(value: str | int | float) -> int:
    if isinstance(value, (int, float)):
        timestamp = int(value)
    else:
        text = str(value).strip()
        try:
            timestamp = int(float(text))
        except ValueError:
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError(f"Invalid period: {value}") from error
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            timestamp = int(parsed.timestamp())
    if timestamp <= 0:
        raise ValueError(f"Period must be a positive Unix timestamp: {value}")
    return timestamp


def validate_request_range(start: int, end: int, resolution: str, max_candles: int) -> None:
    if resolution not in RESOLUTION_SECONDS:
        raise ValueError(f"Unsupported resolution: {resolution}")
    if end <= start:
        raise ValueError("end must be after start")
    if max_candles <= 0:
        raise ValueError("max_candles must be positive")
    requested = (end - start + RESOLUTION_SECONDS[resolution] - 1) // RESOLUTION_SECONDS[resolution]
    if requested > max_candles:
        raise ValueError(
            f"Requested range contains about {requested} candles, above max_candles={max_candles}; "
            "choose a shorter range explicitly"
        )


def _response_payload(response: Any) -> dict[str, Any]:
    raw = response.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise HistoricalDataError("Delta returned a non-JSON response") from error
    if not isinstance(payload, dict):
        raise HistoricalDataError("Delta returned an invalid response object")
    if payload.get("success") is False:
        raise HistoricalDataError(f"Delta historical candle request failed: {payload}")
    return payload


def parse_historical_rows(payload: dict[str, Any]) -> pd.DataFrame:
    rows = payload.get("result")
    if not isinstance(rows, list):
        raise HistoricalDataError(f"Delta response did not contain a candle list: {payload}")
    candles = [parse_candle_message(row) for row in rows]
    candles = [candle for candle in candles if candle is not None]
    if not candles:
        raise HistoricalDataError("Delta returned no valid historical candles")
    frame = pd.DataFrame([candle.as_dict() for candle in candles])
    frame = frame.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    return validate_ohlcv(frame)


def download_historical_candles(
    symbol: str,
    start: str | int | float,
    end: str | int | float,
    resolution: str = "1m",
    max_candles: int = DEFAULT_MAX_CANDLES,
    opener: Callable[..., Any] = urlopen,
    timeout: float = 15.0,
) -> pd.DataFrame:
    if not symbol or any(character.isspace() for character in symbol):
        raise ValueError("symbol must be a non-empty market symbol")
    start_timestamp = parse_period(start)
    end_timestamp = parse_period(end)
    validate_request_range(start_timestamp, end_timestamp, resolution, max_candles)
    query = urlencode({
        "resolution": resolution,
        "symbol": symbol,
        "start": start_timestamp,
        "end": end_timestamp,
    })
    request = Request(f"{REST_CANDLES_URL}?{query}", headers={"Accept": "application/json"})
    try:
        with opener(request, timeout=timeout) as response:
            payload = _response_payload(response)
    except HistoricalDataError:
        raise
    except Exception as error:
        raise HistoricalDataError(f"Delta historical candle request failed: {error}") from error
    frame = parse_historical_rows(payload)
    if len(frame) > max_candles:
        raise HistoricalDataError(
            f"Delta returned {len(frame)} candles, above max_candles={max_candles}"
        )
    return frame


def save_candles(frame: pd.DataFrame, path: str | Path) -> Path:
    validated = validate_ohlcv(frame)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    validated.to_csv(target, index=False)
    return target


def load_candles(path: str | Path) -> pd.DataFrame:
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(target)
    return validate_ohlcv(pd.read_csv(target))


def format_backtest_report(
    result: BacktestResult,
    frame: pd.DataFrame,
    symbol: str,
    resolution: str,
    include_trades: bool = False,
) -> str:
    timestamps = frame.get("timestamp")
    start = _format_timestamp(timestamps.iloc[0]) if timestamps is not None else "unknown"
    end = _format_timestamp(timestamps.iloc[-1]) if timestamps is not None else "unknown"
    report = "\n".join([
        "DELTA HISTORICAL PAPER BACKTEST",
        "SIGNAL/PAPER SIMULATION ONLY — NO ORDERS",
        "----------------------------------------",
        f"Symbol: {symbol}",
        f"Timeframe: {resolution}",
        "Fee model:",
        f"Entry: {result.entry_fee_type.upper()} {result.maker_fee_rate if result.entry_fee_type == 'maker' else result.taker_fee_rate:.4f}",
        f"Exit: {result.exit_fee_type.upper()} {result.maker_fee_rate if result.exit_fee_type == 'maker' else result.taker_fee_rate:.4f}",
        f"Start: {start}",
        f"End: {end}",
        f"Candles: {len(frame)}",
        f"Total trades: {result.total_trades}",
        f"Winning trades: {result.winning_trades}",
        f"Losing trades: {result.losing_trades}",
        f"Win rate: {result.win_rate:.4f}",
        f"Gross P&L: {result.gross_pnl:.8f}",
        f"Total fees: {result.total_fees:.8f}",
        f"Net P&L: {result.net_pnl:.8f}",
        f"Maximum drawdown: {result.maximum_drawdown:.8f}",
        f"Final balance: {result.final_balance:.8f}",
        "Past backtest results do not predict future profitability.",
    ])
    if not include_trades:
        return report

    trades = result.trades
    long_count = sum(trade.side == "LONG" for trade in trades)
    short_count = sum(trade.side == "SHORT" for trade in trades)
    stop_count = sum(trade.exit_reason == "STOP_LOSS" for trade in trades)
    target_count = sum(trade.exit_reason == "TAKE_PROFIT" for trade in trades)
    average_net = sum(trade.net_pnl for trade in trades) / len(trades) if trades else 0.0
    largest_winner = max((trade.net_pnl for trade in trades), default=0.0)
    largest_loser = min((trade.net_pnl for trade in trades), default=0.0)
    lines = [
        report,
        "",
        "TRADE SUMMARY",
        f"LONG trades: {long_count}",
        f"SHORT trades: {short_count}",
        f"STOP LOSS exits: {stop_count}",
        f"TAKE PROFIT exits: {target_count}",
        f"Average net P&L per trade: {average_net:.8f}",
        f"Total fees: {result.total_fees:.8f}",
        f"Largest winning trade: {largest_winner:.8f}",
        f"Largest losing trade: {largest_loser:.8f}",
        "",
        "TRADE REPORT",
        "Trade # | Side | Entry time | Entry price | Exit time | Exit price | Stop Loss | Take Profit | Quantity | Gross P&L | Entry fee | Exit fee | Total fee | Net P&L | Exit reason",
    ]
    lines.extend(_format_trade(trade) for trade in trades)
    return "\n".join(lines)


def _format_trade(trade: TradeReport) -> str:
    return (
        f"{trade.trade_number} | {trade.side} | {_format_timestamp(trade.entry_time)} | "
        f"{trade.entry_price:.8f} | {_format_timestamp(trade.exit_time)} | "
        f"{trade.exit_price:.8f} | {trade.stop_loss:.8f} | {trade.take_profit:.8f} | "
        f"{trade.quantity:.8f} | {trade.gross_pnl:.8f} | {trade.entry_fee:.8f} | "
        f"{trade.exit_fee:.8f} | {trade.total_fee:.8f} | {trade.net_pnl:.8f} | {trade.exit_reason}"
    )


def _format_timestamp(value: Any) -> str:
    return datetime.fromtimestamp(float(value), timezone.utc).isoformat()


def run_historical_backtest(
    symbol: str,
    start: str | int | float,
    end: str | int | float,
    resolution: str = "1m",
    csv_path: str | Path | None = None,
    max_candles: int = DEFAULT_MAX_CANDLES,
    opener: Callable[..., Any] = urlopen,
    include_trades: bool = False,
) -> tuple[pd.DataFrame, BacktestResult, str]:
    frame = download_historical_candles(symbol, start, end, resolution, max_candles, opener)
    if csv_path is not None:
        save_candles(frame, csv_path)
    settings = Settings.from_env()
    result = run_backtest(
        frame,
        initial_balance=settings.initial_balance,
        contract_value=settings.contract_value,
        fee_rate=settings.fee_rate,
        maker_fee_rate=settings.maker_fee_rate,
        taker_fee_rate=settings.taker_fee_rate,
        entry_fee_type=settings.entry_fee_type,
        exit_fee_type=settings.exit_fee_type,
    )
    return frame, result, format_backtest_report(result, frame, symbol, resolution, include_trades)


def main(argv=None) -> int:
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(description="Download public XAUTUSD candles and run a paper backtest.")
    parser.add_argument("--symbol", default=settings.symbol)
    parser.add_argument("--resolution", default="1m", choices=sorted(RESOLUTION_SECONDS))
    parser.add_argument("--start", required=True, help="UTC ISO-8601 or Unix timestamp")
    parser.add_argument("--end", required=True, help="UTC ISO-8601 or Unix timestamp")
    parser.add_argument("--output", type=Path, default=Path("data") / "XAUTUSD_1m.csv")
    parser.add_argument("--max-candles", type=int, default=DEFAULT_MAX_CANDLES)
    parser.add_argument("--trades", action="store_true", help="Print the detailed trade report")
    args = parser.parse_args(argv)

    frame, result, report = run_historical_backtest(
        args.symbol, args.start, args.end, args.resolution, args.output, args.max_candles,
        include_trades=args.trades,
    )
    print(f"Saved validated candles to {args.output}.")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
