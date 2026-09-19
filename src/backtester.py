"""Candle-by-candle paper backtester with explicit P&L accounting."""
from dataclasses import dataclass
import pandas as pd
from .indicators import atr
from .market_data import load_ohlcv_csv, validate_ohlcv
from .portfolio import Portfolio
from .risk_manager import RiskManager
from .strategy import Signal, generate_signal
from .paper_trader import PaperTrader


@dataclass
class BacktestResult:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    gross_pnl: float
    entry_fees: float
    exit_fees: float
    total_fees: float
    net_pnl: float
    maximum_drawdown: float
    final_balance: float


def run_backtest(frame: pd.DataFrame, initial_balance=10000.0, fee_rate=.0005):
    data = validate_ohlcv(frame)
    portfolio = Portfolio(initial_balance, fee_rate)
    risk = RiskManager()
    trader = PaperTrader(portfolio, risk)
    wins = losses = 0
    peak = portfolio.equity
    max_dd = 0.0

    for i in range(1, len(data)):
        row = data.iloc[i]
        window = data.iloc[:i + 1]
        for index in range(len(portfolio.positions) - 1, -1, -1):
            before = portfolio.realized_pnl
            trader.check_exit(index, float(row.close))
            if portfolio.realized_pnl != before:
                trade_net = portfolio.realized_pnl - before
                wins += trade_net > 0
                losses += trade_net <= 0

        signal = generate_signal(window)
        if signal != Signal.HOLD and len(portfolio.positions) < risk.max_open_positions:
            current_atr = atr(window, 14).iloc[-1]
            if pd.notna(current_atr) and current_atr > 0:
                entry = float(row.close)
                stop = entry - 2 * current_atr if signal == Signal.LONG else entry + 2 * current_atr
                try:
                    plan = risk.create_plan(signal, portfolio.equity, entry, stop,
                                            open_positions=len(portfolio.positions))
                    trader.execute(plan)
                except ValueError:
                    pass

        peak = max(peak, portfolio.equity)
        max_dd = max(max_dd, peak - portfolio.equity)

    # Close remaining positions at the final close so results are fully realized.
    for index in range(len(portfolio.positions) - 1, -1, -1):
        before = portfolio.realized_pnl
        portfolio.close_position(index, float(data.close.iloc[-1]))
        trade_net = portfolio.realized_pnl - before
        wins += trade_net > 0
        losses += trade_net <= 0

    total = wins + losses
    return BacktestResult(
        total_trades=total,
        winning_trades=wins,
        losing_trades=losses,
        win_rate=wins / total if total else 0.0,
        gross_pnl=portfolio.gross_realized_pnl,
        entry_fees=portfolio.entry_fees,
        exit_fees=portfolio.exit_fees,
        total_fees=portfolio.fees,
        net_pnl=portfolio.realized_pnl,
        maximum_drawdown=max_dd,
        final_balance=portfolio.balance,
    )


def backtest_csv(path):
    return run_backtest(load_ohlcv_csv(path))
