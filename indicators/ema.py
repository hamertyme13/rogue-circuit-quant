import pandas as pd

from indicators.base import Indicator


class EMA(Indicator):

    def calculate(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        column = f"EMA_{self.period}"

        df[column] = (
            df["close"]
            .ewm(
                span=self.period,
                adjust=False,
            )
            .mean()
        )

        return df