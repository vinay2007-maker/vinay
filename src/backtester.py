"""Candle-by-candle paper backtester with explicit P&L accounting."""
from dataclasses import dataclass, field
import pandas as pd
from .indicators import atr
from .market_data import load_ohlcv_csv, validate_ohlcv
from .portfolio import Portfolio
from .risk_manager import RiskManager
from .strategy import Signal, generate_signal
from .paper_trader import PaperTrader


@dataclass
class TradeReport:
    trade_number: int
    side: str
    entry_time: object
    entry_price: float
    exit_time: object
    exit_price: float
    stop_loss: float
    take_profit: float
    quantity: float
    gross_pnl: float
    entry_fee: float
    exit_fee: float
    total_fee: float
    net_pnl: float
    exit_reason: str


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
    trades: list[TradeReport] = field(default_factory=list)


def run_backtest(frame: pd.DataFrame, initial_balance=10000.0, fee_rate=.0005, contract_value=.001):
    data = validate_ohlcv(frame)
    portfolio = Portfolio(initial_balance, fee_rate, contract_value)
    risk = RiskManager(contract_value=contract_value)
    trader = PaperTrader(portfolio, risk)
    wins = losses = 0
    trades = []
    entry_times = {}
    peak = portfolio.equity
    max_dd = 0.0

    for i in range(1, len(data)):
        row = data.iloc[i]
        window = data.iloc[:i]
        current_time = row.get("timestamp", i)
        for index in range(len(portfolio.positions) - 1, -1, -1):
            position = portfolio.positions[index]
            before = portfolio.realized_pnl
            before_gross = portfolio.gross_realized_pnl
            before_exit_fees = portfolio.exit_fees
            exit_price = float(row.close)
            exit_reason = trader.check_exit(index, exit_price)
            if portfolio.realized_pnl != before:
                trade_net = portfolio.realized_pnl - before
                exit_price = position.stop_loss if exit_reason == "STOP_LOSS" else position.take_profit if exit_reason == "TAKE_PROFIT" else exit_price
                trades.append(_trade_report(
                    len(trades) + 1, position, entry_times.pop(id(position), i),
                    current_time, exit_price, exit_reason or "OTHER",
                    portfolio.gross_realized_pnl - before_gross,
                    portfolio.exit_fees - before_exit_fees, trade_net,
                ))
                wins += trade_net > 0
                losses += trade_net <= 0

        signal = generate_signal(window)
        if signal != Signal.HOLD and len(portfolio.positions) < risk.max_open_positions:
            current_atr = atr(window, 14).iloc[-1]
            if pd.notna(current_atr) and current_atr > 0:
                entry = float(row.open)
                stop = entry - 2 * current_atr if signal == Signal.LONG else entry + 2 * current_atr
                try:
                    plan = risk.create_plan(signal, portfolio.equity, entry, stop,
                                            open_positions=len(portfolio.positions))
                    position = trader.execute(plan)
                    entry_times[id(position)] = current_time
                except ValueError:
                    pass

        marked_prices = {index: float(row.close) for index in range(len(portfolio.positions))}
        equity = portfolio.equity_at(marked_prices)
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    # Close remaining positions at the final close so results are fully realized.
    for index in range(len(portfolio.positions) - 1, -1, -1):
        position = portfolio.positions[index]
        before = portfolio.realized_pnl
        before_gross = portfolio.gross_realized_pnl
        before_exit_fees = portfolio.exit_fees
        exit_price = float(data.close.iloc[-1])
        portfolio.close_position(index, exit_price)
        trade_net = portfolio.realized_pnl - before
        trades.append(_trade_report(
            len(trades) + 1, position, entry_times.pop(id(position), len(data) - 1),
            data.iloc[-1].get("timestamp", len(data) - 1), exit_price, "FINAL CLOSE",
            portfolio.gross_realized_pnl - before_gross,
            portfolio.exit_fees - before_exit_fees, trade_net,
        ))
        wins += trade_net > 0
        losses += trade_net <= 0

    equity = portfolio.equity
    peak = max(peak, equity)
    max_dd = max(max_dd, peak - equity)

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
        trades=trades,
    )


def _trade_report(number, position, entry_time, exit_time, exit_price, reason,
                  gross_pnl, exit_fee, net_pnl):
    return TradeReport(
        trade_number=number,
        side=position.side,
        entry_time=entry_time,
        entry_price=position.entry_price,
        exit_time=exit_time,
        exit_price=exit_price,
        stop_loss=position.stop_loss,
        take_profit=position.take_profit,
        quantity=position.quantity,
        gross_pnl=gross_pnl,
        entry_fee=position.entry_fee,
        exit_fee=exit_fee,
        total_fee=position.entry_fee + exit_fee,
        net_pnl=net_pnl,
        exit_reason=reason,
    )


def backtest_csv(path):
    return run_backtest(load_ohlcv_csv(path))
