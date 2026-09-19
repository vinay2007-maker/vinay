# Delta AI Trading Bot — paper trading only

Educational prototype. It has no Delta Exchange connection, reads no credentials, and contains no live order execution. The baseline EMA-crossover/RSI strategy is not a profitability claim.

## Run
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m src.main
pytest -q
```

## Architecture
`market_data` validates simulated or CSV OHLCV -> `indicators` calculates features -> `strategy` emits LONG/SHORT/HOLD -> `risk_manager` validates a paper `TradePlan` -> `paper_trader` simulates execution and exits -> `portfolio` records balance, equity, P&L and fees. `backtester.run_backtest` applies this flow candle by candle.

Quantity is measured in base units (BTC/contracts), not currency. Maximum loss before fees is `quantity * abs(entry-stop)`; quantity is capped at 1% of equity risk and `max_position_size`. Fees are simulated on entry and exit.

## Historical data
CSV files must contain positive `open,high,low,close,volume` columns. Use `from src.backtester import backtest_csv; print(backtest_csv('data.csv'))`.

## Limitations
This is not financial advice and does not claim profitability. Backtests can differ from real execution and currently use simplified fills, no slippage, and conservative close-price processing. Before any live consideration, perform extensive validation, slippage/liquidity modeling, operational/security review, and a separately reviewed exchange adapter. Never commit secrets.
