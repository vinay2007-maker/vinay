"""Paper execution only; quantities are Delta contract counts."""
from .portfolio import Portfolio, Position
from .risk_manager import RiskManager, TradePlan
class PaperTrader:
    def __init__(self, portfolio: Portfolio, risk_manager: RiskManager): self.portfolio, self.risk_manager = portfolio, risk_manager
    def execute(self, plan: TradePlan) -> Position:
        if self.risk_manager.kill_switch: raise ValueError("kill switch enabled")
        if len(self.portfolio.positions) >= self.risk_manager.max_open_positions: raise ValueError("maximum open positions reached")
        return self.portfolio.open_position(plan.signal.value, plan.entry, plan.quantity, plan.stop_loss, plan.take_profit)
    def check_exit(self, index, price):
        p = self.portfolio.positions[index]
        if (p.side == "LONG" and price <= p.stop_loss) or (p.side == "SHORT" and price >= p.stop_loss):
            self.portfolio.close_position(index, p.stop_loss); return "STOP_LOSS"
        if (p.side == "LONG" and price >= p.take_profit) or (p.side == "SHORT" and price <= p.take_profit):
            self.portfolio.close_position(index, p.take_profit); return "TAKE_PROFIT"
        return None
