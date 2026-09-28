from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AllocationDecision:
    symbol: str
    allowed: bool
    requested_notional: float
    approved_notional: float
    portfolio_exposure: float
    portfolio_exposure_limit: float
    asset_exposure_limit: float
    cash_reserve: float
    reason: str

    def as_dict(self):
        return asdict(self)


class PortfolioAllocator:
    def __init__(
        self,
        max_open_positions: int = 3,
        max_portfolio_exposure: float = 0.30,
        max_asset_exposure: float = 0.10,
        min_cash_reserve: float = 0.20,
    ):
        self.max_open_positions = int(max_open_positions)
        self.max_portfolio_exposure = float(max_portfolio_exposure)
        self.max_asset_exposure = float(max_asset_exposure)
        self.min_cash_reserve = float(min_cash_reserve)

    def allocate(
        self,
        portfolio,
        symbol: str,
        requested_notional: float,
        max_order_notional: float,
    ) -> AllocationDecision:
        equity = max(float(portfolio.account_value()), 0.0)
        invested = max(float(portfolio.position_value()), 0.0)
        cash = max(float(portfolio.cash), 0.0)
        reserve = equity * self.min_cash_reserve
        portfolio_limit = equity * self.max_portfolio_exposure
        asset_limit = equity * self.max_asset_exposure
        existing = portfolio.open_position_for(symbol)
        asset_invested = float(existing.entry_notional) if existing else 0.0
        reasons = []

        if existing is None and portfolio.open_positions() >= self.max_open_positions:
            reasons.append(
                f"Maximum of {self.max_open_positions} open markets reached."
            )

        available = min(
            float(requested_notional),
            float(max_order_notional),
            max(0.0, portfolio_limit - invested),
            max(0.0, asset_limit - asset_invested),
            max(0.0, cash - reserve),
        )
        if available <= 0:
            reasons.append("No allocation remains after exposure and cash limits.")

        approved = max(0.0, available)
        return AllocationDecision(
            symbol=symbol,
            allowed=not reasons and approved > 0,
            requested_notional=float(requested_notional),
            approved_notional=approved,
            portfolio_exposure=(invested / equity if equity else 0.0),
            portfolio_exposure_limit=self.max_portfolio_exposure,
            asset_exposure_limit=self.max_asset_exposure,
            cash_reserve=reserve,
            reason=" ".join(reasons) if reasons else "Allocation approved.",
        )
