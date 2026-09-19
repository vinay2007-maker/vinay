"""Virtual portfolio accounting. Quantity is base units (BTC/contracts)."""
from dataclasses import dataclass
@dataclass
class Position:
    side: str; entry_price: float; quantity: float; stop_loss: float; take_profit: float; entry_fee: float
class Portfolio:
    def __init__(self, initial_balance=10000.0, fee_rate=.0005):
        if initial_balance <= 0 or fee_rate < 0: raise ValueError("invalid portfolio settings")
        self.initial_balance = self.balance = float(initial_balance); self.fee_rate = fee_rate
        self.positions = []; self.realized_pnl = self.fees = 0.0
    def open_position(self, side, entry_price, quantity, stop_loss, take_profit):
        if side not in ("LONG", "SHORT") or entry_price <= 0 or quantity <= 0: raise ValueError("invalid position")
        fee = entry_price * quantity * self.fee_rate; self.balance -= fee; self.fees += fee
        position = Position(side, entry_price, quantity, stop_loss, take_profit, fee); self.positions.append(position); return position
    @staticmethod
    def pnl_for(position, exit_price):
        if exit_price <= 0: raise ValueError("exit price must be positive")
        return ((exit_price - position.entry_price) if position.side == "LONG" else (position.entry_price - exit_price)) * position.quantity
    def unrealized_pnl(self, prices=None):
        prices = prices or {}; return sum(self.pnl_for(p, prices.get(i, p.entry_price)) for i, p in enumerate(self.positions))
    def close_position(self, index, exit_price):
        position = self.positions.pop(index); gross = self.pnl_for(position, exit_price)
        exit_fee = exit_price * position.quantity * self.fee_rate; self.balance += gross - exit_fee; self.fees += exit_fee
        net = gross - position.entry_fee - exit_fee; self.realized_pnl += net; return net
    @property
    def equity(self): return self.balance + self.unrealized_pnl()
