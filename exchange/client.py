"""
Kraken Client

Responsible only for communicating with Kraken.
"""

import ccxt


class KrakenClient:

    def __init__(self):

        self.exchange = ccxt.kraken({
            "enableRateLimit": True,
        })

    def load_markets(self):
        """Load all available Kraken markets."""
        return self.exchange.load_markets()

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 720,
    ):
        """Download OHLCV candles."""
        return self.exchange.fetch_ohlcv(
            symbol,
            timeframe=timeframe,
            limit=limit,
        )

    def fetch_ticker(
        self,
        symbol: str,
    ):
        """Get current ticker."""
        return self.exchange.fetch_ticker(symbol)

    def fetch_balance(self):
        """Will be used later after API keys are added."""
        return self.exchange.fetch_balance()