"""Virtual portfolio accounting where quantity is a number of contracts."""
from dataclasses import dataclass


@dataclass
class Position:
    """Open paper position; quantity counts contracts, not XAUT units."""
    side: str
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    entry_fee: float
    contract_value: float = 0.001


class Portfolio:
    def __init__(self, initial_balance=10000.0, fee_rate=.0005, contract_value=.001):
        if initial_balance <= 0 or fee_rate < 0 or contract_value <= 0:
            raise ValueError("invalid portfolio settings")
        self.initial_balance = self.balance = float(initial_balance)
        self.fee_rate = fee_rate
        self.contract_value = contract_value
        self.positions = []
        self.realized_pnl = 0.0  # net realized P&L after all fees
        self.gross_realized_pnl = 0.0
        self.entry_fees = 0.0
        self.exit_fees = 0.0

    @property
    def fees(self):
        """Total simulated fees, retained for compatibility."""
        return self.entry_fees + self.exit_fees

    def open_position(self, side, entry_price, quantity, stop_loss, take_profit):
        if side not in ("LONG", "SHORT") or entry_price <= 0 or quantity <= 0:
            raise ValueError("invalid position")
        fee = self.notional_for(entry_price, quantity) * self.fee_rate
        self.balance -= fee
        self.entry_fees += fee
        position = Position(side, entry_price, quantity, stop_loss, take_profit, fee, self.contract_value)
        self.positions.append(position)
        return position

    @staticmethod
    def pnl_for(position, exit_price):
        if exit_price <= 0:
            raise ValueError("exit price must be positive")
        return ((exit_price - position.entry_price)
                if position.side == "LONG"
                else (position.entry_price - exit_price)) * position.quantity * position.contract_value

    def notional_for(self, price, quantity):
        return price * quantity * self.contract_value

    def unrealized_pnl(self, prices=None):
        prices = prices or {}
        return sum(self.pnl_for(p, prices.get(i, p.entry_price))
                   for i, p in enumerate(self.positions))

    def close_position(self, index, exit_price):
        position = self.positions.pop(index)
        gross = self.pnl_for(position, exit_price)
        exit_fee = self.notional_for(exit_price, position.quantity) * self.fee_rate
        self.balance += gross - exit_fee
        self.exit_fees += exit_fee
        self.gross_realized_pnl += gross
        net = gross - position.entry_fee - exit_fee
        self.realized_pnl += net
        return net

    @property
    def equity(self):
        return self.equity_at()

    def equity_at(self, prices=None):
        return self.balance + self.unrealized_pnl(prices)
