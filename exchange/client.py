"""
Kraken Client

Responsible only for communicating with Kraken.
"""

import ccxt

from config import KRAKEN_API_KEY, KRAKEN_API_SECRET


class KrakenClient:

    def __init__(self):

        options = {
            "enableRateLimit": True,
        }

        if KRAKEN_API_KEY and KRAKEN_API_SECRET:
            options["apiKey"] = KRAKEN_API_KEY
            options["secret"] = KRAKEN_API_SECRET

        self.exchange = ccxt.kraken(options)

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

    def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
    ):
        """Create a Kraken market order through ccxt."""
        return self.exchange.create_order(
            symbol=symbol,
            type="market",
            side=side.lower(),
            amount=amount,
        )
