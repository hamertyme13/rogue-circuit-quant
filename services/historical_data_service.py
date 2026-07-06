from pathlib import Path

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

        console.print(
            f"Downloading {symbol} ({timeframe})...",
            style="cyan",
        )

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

        console.print(
            f"Saved {len(df)} candles",
            style="green",
        )