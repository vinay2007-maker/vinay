"""Configuration loaded from non-secret environment variables only."""
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    initial_balance: float = 10_000.0
    risk_per_trade: float = 0.01
    max_daily_loss: float = 0.03
    max_open_positions: int = 2
    max_position_size: float = 1.0  # Maximum number of Delta contracts.
    fee_rate: float = 0.0005
    contract_value: float = 0.001  # Each contract represents 0.001 XAUT.
    atr_multiplier: float = 2.0
    risk_reward_ratio: float = 2.0
    symbol: str = "XAUTUSD"

    @classmethod
    def from_env(cls):
        return cls(
            initial_balance=float(os.getenv("PAPER_INITIAL_BALANCE", "10000")),
            risk_per_trade=float(os.getenv("RISK_PER_TRADE", "0.01")),
            max_daily_loss=float(os.getenv("MAX_DAILY_LOSS", "0.03")),
            max_open_positions=int(os.getenv("MAX_OPEN_POSITIONS", "2")),
            max_position_size=float(os.getenv("MAX_POSITION_SIZE", "1")),
            fee_rate=float(os.getenv("PAPER_FEE_RATE", "0.0005")),
            contract_value=float(os.getenv("CONTRACT_VALUE", "0.001")),
            atr_multiplier=float(os.getenv("ATR_MULTIPLIER", "2")),
            risk_reward_ratio=float(os.getenv("RISK_REWARD_RATIO", "2")),
            symbol=os.getenv("PAPER_SYMBOL", "XAUTUSD"),
        )
