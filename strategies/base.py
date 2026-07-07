from abc import ABC, abstractmethod
import pandas as pd

from models.signal import Signal


class Strategy(ABC):

    @abstractmethod
    def generate_signals(
        self,
        df: pd.DataFrame,
    ) -> list[Signal]:
        """Generate trading signals."""
        pass