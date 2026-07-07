from typing import List
import pandas as pd

from indicators.base import Indicator


class IndicatorEngine:

    def __init__(
        self,
        indicators: List[Indicator],
    ):
        self.indicators = indicators

    def calculate(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        for indicator in self.indicators:
            df = indicator.calculate(df)

        return df