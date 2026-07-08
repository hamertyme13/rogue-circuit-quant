from dataclasses import dataclass


USD_ASSETS = {
    "USD",
    "USDC",
    "USDT",
    "ZUSD",
}

ASSET_ALIASES = {
    "XBT": "BTC",
    "XXBT": "BTC",
    "XETH": "ETH",
    "ZUSD": "USD",
}


@dataclass
class BalanceValuation:

    total_value: float
    cash_value: float
    positions_value: float
    positions: dict[str, float]


class KrakenBalanceValuator:

    def __init__(self, client):

        self.client = client

    def snapshot(self) -> BalanceValuation:

        balance = self.client.fetch_balance()
        totals = balance.get("total", {})
        cash_value = 0.0
        positions_value = 0.0
        positions = {}

        for raw_asset, raw_amount in totals.items():
            amount = float(raw_amount or 0)

            if amount == 0:
                continue

            asset = self._normalize_asset(raw_asset)

            if asset in USD_ASSETS:
                cash_value += amount
                positions[asset] = positions.get(asset, 0.0) + amount
                continue

            value = self._value_asset_usd(asset, amount)
            positions_value += value
            positions[asset] = amount

        return BalanceValuation(
            total_value=cash_value + positions_value,
            cash_value=cash_value,
            positions_value=positions_value,
            positions=positions,
        )

    def _value_asset_usd(
        self,
        asset: str,
        amount: float,
    ) -> float:

        ticker = self.client.fetch_ticker(f"{asset}/USD")
        price = ticker.get("last") or ticker.get("close")

        if price is None:
            raise ValueError(
                f"Could not price {asset}/USD from Kraken ticker."
            )

        return amount * float(price)

    def _normalize_asset(self, asset: str) -> str:

        clean = asset.upper()
        return ASSET_ALIASES.get(clean, clean)
