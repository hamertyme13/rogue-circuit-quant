from dataclasses import dataclass


EXCLUDED_BASE_ASSETS = {
    "USD", "USDC", "USDT", "DAI", "EUR", "GBP", "CAD", "AUD", "JPY",
}


@dataclass(frozen=True)
class MarketSelection:
    selected: tuple[str, ...]
    rejected: tuple[dict, ...]


class DiversifiedMarketSelector:
    def select(
        self,
        opportunities,
        limit: int,
        health_by_symbol=None,
    ) -> MarketSelection:
        health_by_symbol = health_by_symbol or {}
        ranked = sorted(
            opportunities,
            key=lambda item: (float(item.score), float(item.confidence)),
            reverse=True,
        )
        selected = []
        seen_bases = set()
        rejected = []

        for item in ranked:
            base = item.symbol.split("/")[0].upper()
            health = health_by_symbol.get(item.symbol)
            reason = ""
            if health is not None and health.status == "quarantined":
                reason = "Rolling paper and shadow evidence quarantined this market."
            elif base in EXCLUDED_BASE_ASSETS:
                reason = "Cash and stablecoin bases are excluded."
            elif base in seen_bases:
                reason = "Another quote market for this asset ranked higher."
            elif int(item.trades) <= 0:
                reason = "Backtest produced no completed trades."
            elif float(item.score) <= 0:
                reason = "Risk-adjusted score is not positive."

            if reason:
                rejected.append({"symbol": item.symbol, "reason": reason})
                continue

            selected.append(item.symbol)
            seen_bases.add(base)
            if len(selected) >= limit:
                break

        return MarketSelection(tuple(selected), tuple(rejected))
