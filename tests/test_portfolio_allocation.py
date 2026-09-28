from datetime import datetime, timezone

from live.trader import AutomatedKrakenTrader
from models.signal import Signal
from risk.allocation import PortfolioAllocator
from risk.portfolio import Portfolio
from risk.position_manager import PositionManager


def _signal(price=100.0):
    return Signal(
        timestamp=datetime.now(timezone.utc),
        action="BUY",
        price=price,
        confidence=0.95,
        strategy="Momentum",
    )


def test_allocator_preserves_cash_and_total_exposure():
    portfolio = Portfolio(1_000)
    allocator = PortfolioAllocator(
        max_open_positions=3,
        max_portfolio_exposure=0.30,
        max_asset_exposure=0.10,
        min_cash_reserve=0.20,
    )

    decision = allocator.allocate(portfolio, "BTC/USD", 250, 250)

    assert decision.allowed is True
    assert decision.approved_notional == 100
    assert decision.cash_reserve == 200


def test_allocator_blocks_after_open_market_limit():
    portfolio = Portfolio(1_000)
    manager = PositionManager(portfolio)
    manager.open_position("BTC/USD", _signal(), 1)
    manager.open_position("ETH/USD", _signal(), 1)
    allocator = PortfolioAllocator(max_open_positions=2)

    decision = allocator.allocate(portfolio, "SOL/USD", 50, 250)

    assert decision.allowed is False
    assert "Maximum of 2" in decision.reason


def test_invested_cash_is_not_counted_as_daily_loss():
    portfolio = Portfolio(1_000)
    PositionManager(portfolio).open_position("BTC/USD", _signal(), 2)

    assert portfolio.daily_loss_percent() < 0.01


def test_paper_trader_can_open_three_distinct_markets():
    trader = AutomatedKrakenTrader()
    trader.max_order_notional = 250

    events = [
        trader._execute_signal(symbol, _signal(price=100))
        for symbol in ("BTC/USD", "ETH/USD", "SOL/USD")
    ]

    assert all(event.executed for event in events)
    assert trader.portfolio.open_positions() == 3
    assert set(trader.last_allocation_decisions) == {
        "BTC/USD", "ETH/USD", "SOL/USD",
    }
