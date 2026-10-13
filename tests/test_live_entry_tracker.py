from datetime import datetime, timezone
import pytest

import live.trader as trader_module

from accounting.ledger import InvestmentLedger
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


def test_trader_stops_between_markets_when_service_requests_stop():
    trader = AutomatedKrakenTrader()
    trader.symbols = ["BTC/USD", "ETH/USD"]
    checked = []
    trader._run_symbol = lambda symbol: checked.append(symbol) or trader._execute_signal(
        symbol, signal(action="HOLD")
    )
    trader.stop_requested = lambda: bool(checked)

    events = trader.run_once()

    assert checked == ["BTC/USD"]
    assert len(events) == 1
    assert "stopped" in trader.last_cycle_note


def test_trader_ends_cycle_after_time_budget(monkeypatch):
    trader = AutomatedKrakenTrader()
    trader.symbols = ["BTC/USD", "ETH/USD"]
    trader.cycle_deadline_seconds = 1
    checked = []
    trader._run_symbol = lambda symbol: checked.append(symbol) or trader._execute_signal(
        symbol, signal(action="HOLD")
    )
    times = iter([0, 0, 2])
    monkeypatch.setattr("live.trader.time.monotonic", lambda: next(times))

    events = trader.run_once()

    assert checked == ["BTC/USD"]
    assert len(events) == 1
    assert "time budget" in trader.last_cycle_note


def test_market_scan_stops_before_next_symbol_after_time_budget(monkeypatch):
    trader = AutomatedKrakenTrader()
    trader.cycle_deadline_seconds = 1
    checked = []

    def fetch(symbol):
        checked.append(symbol)
        raise RuntimeError("unavailable")

    trader._fetch_market_frame = fetch
    times = iter([0, 0, 2])
    monkeypatch.setattr("live.trader.time.monotonic", lambda: next(times))

    result = trader.scan_markets(["BTC/USD", "ETH/USD"])

    assert result == []
    assert checked == ["BTC/USD"]
    assert "time budget" in trader.last_scan_note


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

        def validate_market_order(self, symbol, side, amount):
            assert (symbol, side) == ("BTC/USD", "buy")
            return {"error": [], "result": {"descr": {"order": "validated"}}}

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


def test_shadow_buy_ignores_paper_position_and_uses_kraken_balance():
    class ShadowClient:
        def market(self, symbol):
            return {
                "base": "BTC",
                "quote": "USD",
                "limits": {"amount": {"min": 0.0001}},
            }

        def fetch_balance(self):
            return {"free": {"USD": 10}}

        def amount_to_precision(self, symbol, quantity):
            return f"{quantity:.4f}"

        def validate_market_order(self, symbol, side, amount):
            assert (symbol, side) == ("BTC/USD", "buy")
            return {"error": [], "result": {"descr": {"order": "validated"}}}

        def create_market_order(self, *args, **kwargs):
            raise AssertionError("Shadow mode must not submit an order.")

    trader = AutomatedKrakenTrader(client=ShadowClient())
    trader.positions.open_position(
        "BTC/USD",
        signal(price=100),
        1,
    )
    trader.set_execution_mode("shadow")

    event = trader._execute_signal(
        "BTC/USD",
        signal(price=50_000, confidence=0.95),
    )

    assert event.order_status == "validated"
    assert event.executed is False
    assert event.quantity == 0.0001
    assert "no Kraken order sent" in event.reason


def test_shadow_buy_marks_failed_exchange_dry_run_invalid():
    class ShadowClient:
        def market(self, symbol):
            return {"base": "BTC", "quote": "USD", "limits": {"amount": {"min": 0.0001}}}

        def fetch_balance(self):
            return {"free": {"USD": 100}}

        def amount_to_precision(self, symbol, quantity):
            return str(quantity)

        def validate_market_order(self, symbol, side, amount):
            raise RuntimeError("minimum cost rejected")

        def create_market_order(self, *args, **kwargs):
            raise AssertionError("Shadow mode must not submit an order.")

    trader = AutomatedKrakenTrader(client=ShadowClient())
    trader.set_execution_mode("shadow")
    event = trader._execute_signal("BTC/USD", signal(price=100))
    assert event.executed is False
    assert "minimum cost rejected" in event.reason
    assert trader.last_order_previews["BTC/USD"]["valid"] is False


def test_limited_live_blocks_buy_without_promoted_symbol():
    trader = AutomatedKrakenTrader()
    trader.set_execution_mode("limited_live")

    event = trader._execute_signal(
        "BTC/USD",
        signal(price=100, confidence=0.95),
    )

    assert event.executed is False
    assert "promotion gates" in event.reason


def test_limited_live_never_sells_a_paper_position():
    trader = AutomatedKrakenTrader()
    trader.positions.open_position("BTC/USD", signal(price=100), 0.05)
    trader.set_execution_mode("limited_live")
    event = trader._sell("BTC/USD", signal(action="SELL", price=100))
    assert event.executed is False
    assert "not opened in this live session" in event.reason
    assert trader.portfolio.has_open_position_for("BTC/USD")


def test_live_order_boundary_caps_and_counts_attempts(monkeypatch, tmp_path):
    class Client:
        def __init__(self):
            self.sent = []
            self.validated = []
            self.reject_validation = False

        def fetch_ticker(self, symbol):
            return {"ask": 100, "bid": 99}

        def fetch_open_orders(self, symbol):
            return []

        def validate_market_order(self, symbol, side, amount):
            self.validated.append((symbol, side, amount))
            if self.reject_validation:
                raise RuntimeError("Kraken rejected dry run")
            return {"result": {"descr": {"order": "validated"}}}

        def create_market_order(self, symbol, side, amount, client_order_id):
            self.sent.append((symbol, side, amount))
            raise TimeoutError("ambiguous submission")

    monkeypatch.setattr(trader_module, "ALLOW_LIVE_TRADING", True)
    client = Client()
    trader = AutomatedKrakenTrader(client=client)
    trader.live_order_journal = InvestmentLedger(tmp_path / "ledger.sqlite3")
    trader.set_execution_mode("limited_live")
    trader.live_symbol_allowlist = {"BTC/USD"}

    trader.emergency_stop()
    with pytest.raises(RuntimeError, match="emergency stop"):
        trader._place_live_order("BTC/USD", "buy", 0.05, "id-stop")
    trader.resume_trading()

    with pytest.raises(RuntimeError, match="order cap"):
        trader._place_live_order("BTC/USD", "buy", 0.11, "id-1")
    assert client.sent == []

    client.reject_validation = True
    with pytest.raises(RuntimeError, match="rejected dry run"):
        trader._place_live_order("BTC/USD", "buy", 0.05, "id-reject")
    assert client.sent == []
    assert trader.live_order_attempts == 0
    client.reject_validation = False

    with pytest.raises(TimeoutError):
        trader._place_live_order("BTC/USD", "buy", 0.05, "id-2")
    assert trader.live_order_attempts == 1
    assert len(client.sent) == 1
    assert len(client.validated) == 2
    assert trader.live_order_journal.live_order_intents()[0]["status"] == "uncertain"

    with pytest.raises(RuntimeError, match="reconcile"):
        trader._place_live_order("BTC/USD", "buy", 0.05, "id-3")
    assert len(client.sent) == 1

    restarted = AutomatedKrakenTrader(client=client)
    restarted.live_order_journal = trader.live_order_journal
    restarted.set_execution_mode("limited_live")
    restarted.live_symbol_allowlist = {"BTC/USD"}
    with pytest.raises(RuntimeError, match="reconciled"):
        restarted._place_live_order("BTC/USD", "buy", 0.05, "id-restart")
    assert len(client.sent) == 1


def test_emergency_stop_after_live_dry_run_prevents_submission(monkeypatch):
    class Client:
        def fetch_ticker(self, symbol):
            return {"ask": 100}

        def fetch_open_orders(self, symbol):
            return []

        def validate_market_order(self, symbol, side, amount):
            trader.emergency_stop()

        def create_market_order(self, *args, **kwargs):
            raise AssertionError("Emergency stop must prevent submission.")

    monkeypatch.setattr(trader_module, "ALLOW_LIVE_TRADING", True)
    trader = AutomatedKrakenTrader(client=Client())
    trader.set_execution_mode("limited_live")
    trader.live_symbol_allowlist = {"BTC/USD"}
    with pytest.raises(RuntimeError, match="emergency stop"):
        trader._place_live_order("BTC/USD", "buy", 0.05, "id-stop")
    assert trader.live_order_attempts == 0


def test_incomplete_live_order_response_stays_uncertain(monkeypatch, tmp_path):
    class Client:
        def fetch_ticker(self, symbol):
            return {"ask": 100}

        def fetch_open_orders(self, symbol):
            return []

        def validate_market_order(self, symbol, side, amount):
            return {"result": {"descr": {"order": "validated"}}}

        def create_market_order(self, *args, **kwargs):
            return {"status": "open"}

    monkeypatch.setattr(trader_module, "ALLOW_LIVE_TRADING", True)
    trader = AutomatedKrakenTrader(client=Client())
    trader.live_order_journal = InvestmentLedger(tmp_path / "ledger.sqlite3")
    trader.set_execution_mode("limited_live")
    trader.live_symbol_allowlist = {"BTC/USD"}
    with pytest.raises(RuntimeError, match="reconcile before retrying"):
        trader._place_live_order("BTC/USD", "buy", 0.05, "ca-incomplete")
    assert trader.live_order_journal.live_order_intents()[0]["status"] == "uncertain"
