from __future__ import annotations

from dataclasses import dataclass, field

from live.trader import TradeCycleEvent
from risk.portfolio import Portfolio


@dataclass(frozen=True)
class PaperValidationConfig:

    min_cycles: int = 100
    min_closed_trades: int = 10
    max_drawdown: float = 0.10
    min_growth: float = 0.0
    min_opportunity_rate: float = 0.05


@dataclass(frozen=True)
class PaperValidationReport:

    cycles: int
    closed_trades: int
    executed_events: int
    opportunity_events: int
    starting_balance: float
    ending_equity: float
    growth: float
    growth_percent: float
    max_drawdown: float
    opportunity_rate: float
    passed: bool
    reasons: list[str] = field(default_factory=list)


class PaperTradingValidator:

    def __init__(
        self,
        config: PaperValidationConfig | None = None,
    ):

        self.config = config or PaperValidationConfig()

    def evaluate(
        self,
        portfolio: Portfolio,
        events: list[TradeCycleEvent],
        cycles: int,
    ) -> PaperValidationReport:

        closed_trades = len(portfolio.closed_trades)
        executed_events = len([
            event
            for event in events
            if event.executed
        ])
        opportunity_events = len([
            event
            for event in events
            if event.opportunity
        ])
        starting_balance = float(portfolio.starting_balance)
        ending_equity = float(portfolio.account_value())
        growth = ending_equity - starting_balance
        growth_percent = (
            growth / starting_balance
            if starting_balance
            else 0.0
        )
        opportunity_rate = (
            opportunity_events / len(events)
            if events
            else 0.0
        )
        max_drawdown = float(portfolio.drawdown_percent())
        reasons = self._reasons(
            cycles=cycles,
            closed_trades=closed_trades,
            growth_percent=growth_percent,
            max_drawdown=max_drawdown,
            opportunity_rate=opportunity_rate,
        )

        return PaperValidationReport(
            cycles=cycles,
            closed_trades=closed_trades,
            executed_events=executed_events,
            opportunity_events=opportunity_events,
            starting_balance=starting_balance,
            ending_equity=ending_equity,
            growth=growth,
            growth_percent=growth_percent,
            max_drawdown=max_drawdown,
            opportunity_rate=opportunity_rate,
            passed=not reasons,
            reasons=reasons,
        )

    def _reasons(
        self,
        cycles: int,
        closed_trades: int,
        growth_percent: float,
        max_drawdown: float,
        opportunity_rate: float,
    ) -> list[str]:

        reasons = []

        if cycles < self.config.min_cycles:
            reasons.append(
                f"Needs at least {self.config.min_cycles} paper cycles."
            )

        if closed_trades < self.config.min_closed_trades:
            reasons.append(
                f"Needs at least {self.config.min_closed_trades} closed trades."
            )

        if growth_percent < self.config.min_growth:
            reasons.append(
                "Paper equity growth is below the required threshold."
            )

        if max_drawdown > self.config.max_drawdown:
            reasons.append(
                "Paper drawdown is above the allowed threshold."
            )

        if opportunity_rate < self.config.min_opportunity_rate:
            reasons.append(
                "Opportunity rate is below the required threshold."
            )

        return reasons
