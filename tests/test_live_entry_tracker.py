from datetime import datetime, timezone

from live.trader import (
    AutomatedKrakenTrader,
    StrategyPerformanceSnapshot,
)
from models.signal import Signal
from risk.portfolio import Portfolio
from risk.position_manager import PositionManager


def signal(
    action="BUY",
    price=100.0,
    confidence=0.9,
    strategy="Momentum",
):
    return Signal(
        timestamp=datetime.now(timezone.utc),
        action=action,
        price=price,
        confidence=confidence,
        strategy=strategy,
    )


def test_position_tracker_moves_cash_and_values_open_entries():
    portfolio = Portfolio(1_000)
    manager = PositionManager(portfolio)

    manager.open_position(
        "BTC/USD",
        signal(price=100),
        2,
    )
    portfolio.update_market_price("BTC/USD", 110)

    assert portfolio.cash < 800
    assert portfolio.position_value() == 220
    assert portfolio.account_value() > portfolio.cash
    assert portfolio.has_open_position_for("BTC/USD") is True


def test_position_tracker_closes_matching_symbol_only():
    portfolio = Portfolio(1_000)
    manager = PositionManager(portfolio)

    manager.open_position(
        "BTC/USD",
        signal(price=100),
        1,
    )
    manager.open_position(
        "ETH/USD",
        signal(price=50),
        1,
    )
    manager.close_position(
        "ETH/USD",
        signal(action="SELL", price=60),
    )

    assert portfolio.has_open_position_for("BTC/USD") is True
    assert portfolio.has_open_position_for("ETH/USD") is False
    assert portfolio.closed_trades[0].symbol == "ETH/USD"


def test_trader_marks_qualified_buy_signal_as_opportunity():
    trader = AutomatedKrakenTrader()
    trader.strategy_performance["BTC/USD"] = StrategyPerformanceSnapshot(
        symbol="BTC/USD",
        strategy="Momentum",
        score=150,
        net_profit=100,
        win_rate=0.7,
        drawdown=0.05,
        trades=10,
        rationale="Strong backtest.",
    )

    event = trader._execute_signal(
        "BTC/USD",
        signal(price=50_000, confidence=0.95),
    )

    assert event.executed is True
    assert event.opportunity is True
    assert "not a profit guarantee" in event.opportunity_reason
    assert trader.portfolio.has_open_position_for("BTC/USD") is True


def test_trader_isolates_market_failure_and_continues_cycle():
    trader = AutomatedKrakenTrader()
    trader.symbols = ["BAD/USD", "BTC/USD"]

    def run_symbol(symbol):
        if symbol == "BAD/USD":
            raise RuntimeError("market unavailable")
        return trader._execute_signal("BTC/USD", signal(action="HOLD"))

    trader._run_symbol = run_symbol

    events = trader.run_once()

    assert len(events) == 2
    assert events[0].strategy == "MarketError"
    assert "market unavailable" in events[0].reason
    assert events[1].symbol == "BTC/USD"
    assert trader.cycles == 1


def test_shadow_mode_validates_buy_without_sending_order():
    class ShadowClient:
        def market(self, symbol):
            return {
                "base": "BTC",
                "quote": "USD",
                "limits": {"amount": {"min": 0.0001}},
            }

        def fetch_balance(self):
            return {"free": {"USD": 1_000}}

        def amount_to_precision(self, symbol, quantity):
            return str(quantity)

        def create_market_order(self, *args, **kwargs):
            raise AssertionError("Shadow mode must not submit an order.")

    trader = AutomatedKrakenTrader(client=ShadowClient())
    trader.set_execution_mode("shadow")

    event = trader._execute_signal(
        "BTC/USD",
        signal(price=100, confidence=0.95),
    )

    assert event.executed is False
    assert event.order_status == "validated"
    assert "no Kraken order sent" in event.reason
    assert "BTC/USD" in trader.last_order_previews
