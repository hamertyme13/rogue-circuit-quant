import pandas as pd

from indicators.base import Indicator


class RSI(Indicator):

    def calculate(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        delta = df["close"].diff()

        gain = delta.clip(lower=0)

        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(self.period).mean()

        avg_loss = loss.rolling(self.period).mean()

        rs = avg_gain / avg_loss

        df[f"RSI_{self.period}"] = (
            100 - (100 / (1 + rs))
        )

        return df