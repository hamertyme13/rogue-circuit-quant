import ccxt

class KrakenClient:

    def __init__(self):

        self.exchange = ccxt.kraken({
            "enableRateLimit": True
        })

    def load_markets(self):
        self.exchange.load_markets()

    def fetch_ohlcv(
        self,
        symbol,
        timeframe,
        limit=720
    ):
        return self.exchange.fetch_ohlcv(
            symbol,
            timeframe=timeframe,
            limit=limit
        )