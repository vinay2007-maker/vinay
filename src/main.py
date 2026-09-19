from .config import Settings
from .market_data import SimulatedMarketData
from .indicators import atr
from .portfolio import Portfolio
from .risk_manager import RiskManager
from .paper_trader import PaperTrader
from .strategy import Signal, generate_signal

def main():
    settings = Settings.from_env(); market = SimulatedMarketData.from_closes([100+i*.2 for i in range(60)])
    signal = generate_signal(market.candles); price = float(market.candles.close.iloc[-1]); volatility = float(atr(market.candles, 14).iloc[-1])
    portfolio = Portfolio(settings.initial_balance, settings.fee_rate); risk = RiskManager(settings.risk_per_trade, settings.max_daily_loss, settings.max_position_size, settings.max_open_positions, settings.risk_reward_ratio)
    print(f"price={price:.2f} signal={signal.value} balance={portfolio.balance:.2f}")
    if signal != Signal.HOLD:
        stop = price-settings.atr_multiplier*volatility if signal == Signal.LONG else price+settings.atr_multiplier*volatility
        plan = risk.create_plan(signal, portfolio.equity, price, stop); PaperTrader(portfolio, risk).execute(plan); print(f"paper {signal.value} qty={plan.quantity:.6f} SL={plan.stop_loss:.2f} TP={plan.take_profit:.2f}")
if __name__ == "__main__": main()
