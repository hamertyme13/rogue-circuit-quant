from dataclasses import dataclass
from datetime import datetime


@dataclass
class Signal:
    timestamp: datetime
    action: str
    price: float
    confidence: float
    strategy: str