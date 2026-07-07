import pandas as pd

from indicators.base import Indicator


class SMA(Indicator):

    def calculate(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        column = f"SMA_{self.period}"

        df[column] = (
            df["close"]
            .rolling(self.period)
            .mean()
        )

        return df