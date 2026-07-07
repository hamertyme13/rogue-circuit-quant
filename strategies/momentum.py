import pandas as pd

from models.signal import Signal
from models.constants import BUY, SELL, HOLD
from strategies.base import Strategy

from indicators.engine import IndicatorEngine
from indicators.ema import EMA
from indicators.rsi import RSI


class MomentumStrategy(Strategy):

    def __init__(
        self,
        fast_ema=20,
        slow_ema=50,
        rsi_period=14,
        buy_rsi=55,
        sell_rsi=45,
    ):

        self.fast_ema = fast_ema
        self.slow_ema = slow_ema
        self.rsi_period = rsi_period

        self.buy_rsi = buy_rsi
        self.sell_rsi = sell_rsi

        self.engine = IndicatorEngine([
            EMA(fast_ema),
            EMA(slow_ema),
            RSI(rsi_period),
        ])

    def generate_signals(self, df: pd.DataFrame):

        df = self.engine.calculate(df)

        latest = df.iloc[-1]

        ema_fast = latest[f"EMA_{self.fast_ema}"]
        ema_slow = latest[f"EMA_{self.slow_ema}"]
        rsi = latest[f"RSI_{self.rsi_period}"]

        signals = []

        if (
            ema_fast > ema_slow
            and rsi > self.buy_rsi
        ):

            signals.append(
                Signal(
                    timestamp=latest["timestamp"],
                    action=BUY,
                    price=latest["close"],
                    confidence=0.80,
                    strategy="Momentum",
                )
            )

        elif (
            ema_fast < ema_slow
            and rsi < self.sell_rsi
        ):

            signals.append(
                Signal(
                    timestamp=latest["timestamp"],
                    action=SELL,
                    price=latest["close"],
                    confidence=0.80,
                    strategy="Momentum",
                )
            )

        if not signals:

            signals.append(
                Signal(
                    timestamp=latest["timestamp"],
                    action=HOLD,
                    price=latest["close"],
                    confidence=0.0,
                    strategy="Momentum",
                )
            )

        return signals