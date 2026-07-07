import pandas as pd

from models.signal import Signal
from strategies.base import Strategy

from indicators.engine import IndicatorEngine
from indicators.ema import EMA
from indicators.rsi import RSI


class MomentumStrategy(Strategy):

    def __init__(self):

        self.engine = IndicatorEngine([
            EMA(20),
            EMA(50),
            RSI(14),
        ])

    def generate_signals(
        self,
        df: pd.DataFrame,
    ) -> list[Signal]:

        df = self.engine.calculate(df)

        signals = []

        latest = df.iloc[-1]

        ema20 = latest["EMA_20"]
        ema50 = latest["EMA_50"]
        rsi = latest["RSI_14"]

        if ema20 > ema50 and rsi > 55:

            signals.append(
                Signal(
                    timestamp=latest["timestamp"],
                    action="BUY",
                    price=latest["close"],
                    confidence=0.75,
                    strategy="Momentum",
                )
            )

        elif ema20 < ema50 and rsi < 45:

            signals.append(
                Signal(
                    timestamp=latest["timestamp"],
                    action="SELL",
                    price=latest["close"],
                    confidence=0.75,
                    strategy="Momentum",
                )
            )

        if not signals:

            signals.append(
                Signal(
                    timestamp=latest["timestamp"],
                    action="HOLD",
                    price=latest["close"],
                    confidence=0.0,
                    strategy="Momentum",
                )
            )
        return signals