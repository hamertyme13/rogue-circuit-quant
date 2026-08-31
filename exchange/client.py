"""
Kraken Client

Responsible only for communicating with Kraken.
"""

import ccxt

from config import KRAKEN_API_KEY, KRAKEN_API_SECRET


class KrakenClient:

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
    ):

        options = {
            "enableRateLimit": True,
        }

        key = api_key or KRAKEN_API_KEY
        secret = api_secret or KRAKEN_API_SECRET

        if key and secret:
            options["apiKey"] = key
            options["secret"] = secret

        self.exchange = ccxt.kraken(options)
        self.has_credentials = bool(key and secret)

    @classmethod
    def from_credentials(cls, credentials: dict[str, str] | None):

        if not credentials:
            return cls()

        return cls(
            api_key=credentials.get("api_key", ""),
            api_secret=credentials.get("api_secret", ""),
        )

    def load_markets(self):
        """Load all available Kraken markets."""
        return self.exchange.load_markets()

    def has_market(self, symbol: str) -> bool:
        """Return whether Kraken exposes a tradable market."""
        return symbol in self.load_markets()

    def market(self, symbol: str) -> dict:
        """Return Kraken market metadata for a symbol."""
        markets = self.load_markets()

        if symbol not in markets:
            raise ValueError(f"{symbol} is not available on Kraken.")

        return markets[symbol]

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

    def fetch_tickers(self, symbols=None):
        """Get tickers used to rank a bounded market scan."""
        return self.exchange.fetch_tickers(symbols)

    def fetch_balance(self):
        """Will be used later after API keys are added."""
        return self.exchange.fetch_balance()

    def fetch_api_key_info(self):
        """Return the active key's permissions and restrictions."""
        method = getattr(self.exchange, "privatePostGetApiKeyInfo", None)
        if method is None:
            method = getattr(self.exchange, "private_post_getapikeyinfo", None)
        if method is None:
            raise RuntimeError("Installed ccxt does not expose GetApiKeyInfo.")
        return method()

    def amount_to_precision(self, symbol: str, amount: float) -> str:
        return self.exchange.amount_to_precision(symbol, amount)

    def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        client_order_id: str = "",
    ):
        """Create a Kraken market order through ccxt."""
        params = {}
        if client_order_id:
            params["cl_ord_id"] = client_order_id

        return self.exchange.create_order(
            symbol=symbol,
            type="market",
            side=side.lower(),
            amount=amount,
            params=params,
        )

    def fetch_order(self, order_id: str, symbol: str):
        return self.exchange.fetch_order(order_id, symbol)

    def fetch_open_orders(self, symbol: str | None = None):
        return self.exchange.fetch_open_orders(symbol)

    def cancel_all_orders(self, symbol: str | None = None):
        return self.exchange.cancel_all_orders(symbol)
