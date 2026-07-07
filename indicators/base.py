"""
Base Indicator Class

Every indicator inherits from this class.
"""

from abc import ABC, abstractmethod
import pandas as pd


class Indicator(ABC):

    def __init__(self, period: int):

        self.period = period

    @abstractmethod
    def calculate(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Calculate indicator."""
        pass