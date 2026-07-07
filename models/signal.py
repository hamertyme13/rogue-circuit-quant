from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass
class Signal:
    timestamp: datetime

    action: Literal[
        "BUY",
        "SELL",
        "HOLD",
    ]

    price: float

    confidence: float

    strategy: str