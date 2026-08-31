from datetime import datetime

from live.paper_validation import (
    PaperTradingValidator,
    PaperValidationConfig,
)
from live.trader import TradeCycleEvent
from models.trade import Trade
from risk.portfolio import Portfolio


def event(
    executed=True,
    opportunity=True,
):
    return TradeCycleEvent(
        symbol="BTC/USD",
        action="BUY",
        confidence=0.9,
        price=100,
        strategy="Test",
        executed=executed,
        opportunity=opportunity,
    )


def winning_portfolio():
    portfolio = Portfolio(starting_balance=1000)
    trade = Trade(
        strategy="Test",
        symbol="BTC/USD",
        entry_time=datetime(2026, 1, 1),
        entry_price=100,
        quantity=1,
    )
    portfolio.open_trade(trade)
    portfolio.close_trade(
        trade,
        exit_price=120,
        exit_time=datetime(2026, 1, 2),
    )

    return portfolio


def test_paper_validator_passes_sufficient_profitable_run():
    report = PaperTradingValidator(
        PaperValidationConfig(
            min_cycles=2,
            min_closed_trades=1,
            min_growth=0.01,
            min_opportunity_rate=0.5,
        )
    ).evaluate(
        portfolio=winning_portfolio(),
        events=[event(), event(executed=False, opportunity=False)],
        cycles=2,
    )

    assert report.passed
    assert report.closed_trades == 1
    assert report.executed_events == 1
    assert report.opportunity_rate == 0.5
    assert report.growth_percent > 0.01


def test_paper_validator_blocks_short_or_unprofitable_run():
    report = PaperTradingValidator(
        PaperValidationConfig(
            min_cycles=10,
            min_closed_trades=3,
            min_growth=0.01,
            min_opportunity_rate=0.5,
        )
    ).evaluate(
        portfolio=Portfolio(starting_balance=1000),
        events=[event(executed=False, opportunity=False)],
        cycles=1,
    )

    assert not report.passed
    assert len(report.reasons) >= 3
    assert "paper cycles" in report.reasons[0]
