from accounting.valuation import KrakenBalanceValuator


class FakeClient:

    def fetch_balance(self):
        return {
            "total": {
                "USD": 100,
                "XBT": 0.5,
                "ETH": 2,
            }
        }

    def fetch_ticker(self, symbol):
        prices = {
            "BTC/USD": {"last": 40_000},
            "ETH/USD": {"last": 2_000},
        }

        return prices[symbol]


def test_kraken_balance_valuator_prices_cash_and_crypto():
    snapshot = KrakenBalanceValuator(FakeClient()).snapshot()

    assert snapshot.cash_value == 100
    assert snapshot.positions_value == 24_000
    assert snapshot.total_value == 24_100
    assert snapshot.positions["BTC"] == 0.5
    assert snapshot.positions["ETH"] == 2
