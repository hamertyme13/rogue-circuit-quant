from dataclasses import dataclass


@dataclass
class OptimizationResult:

    fast_ema: int
    slow_ema: int
    rsi_period: int

    buy_rsi: int
    sell_rsi: int

    trades: int

    win_rate: float

    net_profit: float

    drawdown: float

    