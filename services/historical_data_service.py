from pathlib import Path
from utils.logger import info, success

import pandas as pd
from rich.console import Console

from config import (
    HISTORICAL_DIR,
    CANDLE_LIMIT,
)
from exchange.client import KrakenClient

console = Console()


class HistoricalDataService:

    def __init__(self):

        self.client = KrakenClient()

    def download_symbol(
        self,
        symbol: str,
        timeframe: str,
    ):

        info(f"Downloading {symbol} ({timeframe})...")

        candles = self.client.fetch_ohlcv(
            symbol,
            timeframe,
            CANDLE_LIMIT,
        )

        df = pd.DataFrame(
            candles,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ],
        )
        
        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            unit="ms",
        )

        df = self.validate_data(df)

        folder = HISTORICAL_DIR / symbol.replace("/", "_")
        folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        filename = folder / f"{timeframe}.csv"

        df.to_csv(
            filename,
            index=False,
        )

        success(f"Saved {len(df)} candles")

    def validate_data(self, df):

        if df.empty:
            raise ValueError("Downloaded dataframe is empty.")

        if df.isnull().sum().sum() > 0:
            raise ValueError("Downloaded dataframe contains missing values.")

        if df.duplicated().sum() > 0:
            df = df.drop_duplicates()

        return df