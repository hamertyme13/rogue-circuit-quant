from dataclasses import dataclass
from datetime import datetime


@dataclass
class Trade:
    strategy: str

    entry_time: datetime
    exit_time: datetime | None = None

    entry_price: float = 0.0
    exit_price: float = 0.0

    quantity: float = 0.0

    pnl: float = 0.0

    status: str = "OPEN"