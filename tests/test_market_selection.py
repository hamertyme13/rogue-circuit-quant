from dataclasses import dataclass

from live.market_selection import DiversifiedMarketSelector


@dataclass
class Opportunity:
    symbol: str
    score: float
    confidence: float
    trades: int


def test_selector_keeps_diversified_crypto_markets():
    opportunities = [
        Opportunity("USDT/USD", 500, 0.99, 20),
        Opportunity("BTC/USD", 120, 0.80, 12),
        Opportunity("BTC/USDC", 110, 0.90, 15),
        Opportunity("ETH/USD", 100, 0.75, 10),
        Opportunity("SOL/USD", -1, 0.85, 10),
    ]

    result = DiversifiedMarketSelector().select(opportunities, limit=3)

    assert result.selected == ("BTC/USD", "ETH/USD")
    rejected = {item["symbol"]: item["reason"] for item in result.rejected}
    assert "stablecoin" in rejected["USDT/USD"]
    assert "quote market" in rejected["BTC/USDC"]
    assert "not positive" in rejected["SOL/USD"]


def test_selector_rejects_market_without_test_trades():
    result = DiversifiedMarketSelector().select(
        [Opportunity("ADA/USD", 50, 0.8, 0)],
        limit=1,
    )

    assert result.selected == ()
    assert "no completed trades" in result.rejected[0]["reason"]
