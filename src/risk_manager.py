"""The only trade approval gate. It approves paper plans, never live orders."""
from dataclasses import dataclass
import math
from .strategy import Signal

@dataclass(frozen=True)
class TradePlan:
    """Paper plan whose quantity is a whole number of Delta contracts."""
    signal: Signal; entry: float; quantity: int; stop_loss: float; take_profit: float; risk_amount: float

class RiskManager:
    """Validate paper trades and size quantity in Delta contract counts."""
    def __init__(self, risk_per_trade=.01, max_daily_loss=.03, max_position_size=1.0, max_open_positions=2, risk_reward_ratio=2.0, contract_value=.001):
        if not 0 < risk_per_trade <= .01: raise ValueError("risk_per_trade must be in (0, 0.01]")
        if not 0 < max_daily_loss <= 1 or max_position_size <= 0 or max_open_positions < 0 or risk_reward_ratio <= 0 or contract_value <= 0: raise ValueError("invalid risk settings")
        self.risk_per_trade, self.max_daily_loss = risk_per_trade, max_daily_loss
        self.max_position_size, self.max_open_positions = max_position_size, max_open_positions
        self.risk_reward_ratio, self.contract_value, self.kill_switch = risk_reward_ratio, contract_value, False

    def create_plan(self, signal, equity, entry, stop_loss, take_profit=None, open_positions=0, daily_loss=0.0):
        if self.kill_switch: raise ValueError("kill switch enabled")
        if signal == Signal.HOLD: raise ValueError("HOLD is not tradable")
        if equity <= 0 or entry <= 0 or stop_loss <= 0: raise ValueError("equity, entry and stop must be positive")
        if open_positions >= self.max_open_positions: raise ValueError("maximum open positions reached")
        if daily_loss >= equity * self.max_daily_loss: raise ValueError("daily loss limit reached")
        distance = abs(entry - stop_loss)
        if distance == 0: raise ValueError("stop must differ from entry")
        if signal == Signal.LONG and stop_loss >= entry: raise ValueError("long stop must be below entry")
        if signal == Signal.SHORT and stop_loss <= entry: raise ValueError("short stop must be above entry")
        expected = entry + distance * self.risk_reward_ratio if signal == Signal.LONG else entry - distance * self.risk_reward_ratio
        if take_profit is None: take_profit = expected
        if (signal == Signal.LONG and take_profit <= entry) or (signal == Signal.SHORT and take_profit >= entry): raise ValueError("take-profit is on the wrong side")
        if abs(take_profit - entry) < distance * self.risk_reward_ratio: raise ValueError("take-profit is below configured reward")
        risk_amount = equity * self.risk_per_trade
        per_contract_stop_risk = distance * self.contract_value
        contracts_by_risk = risk_amount / per_contract_stop_risk
        quantity = min(math.floor(contracts_by_risk), math.floor(self.max_position_size))
        if quantity <= 0: raise ValueError("quantity is not positive")
        return TradePlan(signal, entry, quantity, stop_loss, take_profit, quantity * distance * self.contract_value)
