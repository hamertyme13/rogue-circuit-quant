from dataclasses import dataclass
from datetime import datetime


@dataclass
class Trade:
    strategy: str

    entry_time: datetime
    exit_time: datetime | None = None

    symbol: str = ""

    side: str = "LONG"

    entry_price: float = 0.0
    exit_price: float = 0.0

    quantity: float = 0.0

    entry_notional: float = 0.0

    entry_fee: float = 0.0

    exit_fee: float = 0.0

    pnl: float = 0.0

    order_id: str = ""

    order_status: str = ""

    status: str = "OPEN"
