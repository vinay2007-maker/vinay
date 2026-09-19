# Delta AI Trading Bot — paper trading only

Educational prototype. It uses only public Delta Exchange market-data endpoints, reads no credentials, and contains no live order execution. The baseline EMA-crossover/RSI strategy is not a profitability claim.

## Run
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m src.main
pytest -q
```

## Live market-data signals
```bash
python -m src.live_signal
```

This connects only to Delta Exchange public market-data endpoints, warms up
with historical one-minute candles, and listens to the public
`candlestick_1m` WebSocket channel. It prints completed-candle signals and
local proposed paper plans. It does not use API keys, authenticated endpoints,
or any order placement, cancellation, or modification API.

## Historical XAUTUSD backtest
Download validated public candles, save them locally, and run the existing
paper backtester:
```bash
python -m src.historical_backtest --symbol XAUTUSD \
	--resolution 1m \
	--start 2026-01-01T00:00:00Z \
	--end 2026-01-02T00:00:00Z \
	--output data/XAUTUSD_1m.csv
```

The range is bounded by `--max-candles` (10,000 by default), and no alternate
symbol is selected if Delta rejects the requested symbol. The output is a
historical paper simulation only; it is not a prediction of future
profitability.

## Architecture
`market_data` validates simulated or CSV OHLCV -> `indicators` calculates features -> `strategy` emits LONG/SHORT/HOLD -> `risk_manager` validates a paper `TradePlan` -> `paper_trader` simulates execution and exits -> `portfolio` records balance, equity, P&L and fees. `backtester.run_backtest` applies this flow candle by candle.

Quantity is measured in Delta contract counts, not XAUT units or currency. For XAUTUSD, each contract represents `0.001 XAUT`; notional is `price * quantity * contract_value`. Maximum loss before fees is `quantity * abs(entry-stop) * contract_value`; quantity is capped at 1% of equity risk and `max_position_size`. Fees are simulated on entry and exit.

Historical paper backtests use explicit fee settings: `MAKER_FEE_RATE`,
`TAKER_FEE_RATE`, `ENTRY_FEE_TYPE`, and `EXIT_FEE_TYPE`. The default is
conservative taker/taker at `0.0001` per side. `PAPER_FEE_RATE` remains an
explicit legacy override that applies one rate to both sides.

## Historical data
CSV files must contain positive `open,high,low,close,volume` columns. Use `from src.backtester import backtest_csv; print(backtest_csv('data.csv'))`.

## Limitations
This is not financial advice and does not claim profitability. Backtests can differ from real execution and currently use simplified fills, no slippage, and conservative close-price processing. Before any live consideration, perform extensive validation, slippage/liquidity modeling, operational/security review, and a separately reviewed exchange adapter. Never commit secrets.
