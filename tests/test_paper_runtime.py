from datetime import datetime, timezone

from live.paper_runtime import PaperRuntimeState
from live.trader import AutomatedKrakenTrader
from models.signal import Signal


def _signal(action="BUY", price=100.0):
    return Signal(
        timestamp=datetime.now(timezone.utc),
        action=action,
        price=price,
        confidence=0.9,
        strategy="Momentum",
    )


def test_paper_runtime_round_trip_restores_portfolio_and_evidence():
    runtime = PaperRuntimeState()
    source = AutomatedKrakenTrader()
    source.positions.open_position("BTC/USD", _signal(), 1.5)
    source.positions.open_position("ETH/USD", _signal(price=50), 2)
    source.positions.close_position("ETH/USD", _signal("SELL", 60))
    source.portfolio.update_market_price("BTC/USD", 110)
    source.cycles = 14
    evidence = {
        "cycles": 12,
        "total_events": 30,
        "executed_events": 4,
        "opportunity_events": 8,
        "unverified_cycles": 2,
        "legacy_cycles": 0,
    }

    payload = runtime.export(source, evidence)
    restored = AutomatedKrakenTrader()
    restored_evidence, did_restore = runtime.restore(restored, payload)

    assert did_restore is True
    assert restored.portfolio.open_positions() == 1
    assert len(restored.portfolio.closed_trades) == 1
    assert restored.portfolio.open_position_for("BTC/USD").quantity == 1.5
    assert restored.portfolio.market_prices["BTC/USD"] == 110
    assert restored.risk.portfolio is restored.portfolio
    assert restored.positions.portfolio is restored.portfolio
    assert restored_evidence == evidence


def test_paper_runtime_preserves_legacy_portfolio_without_counting_old_cycles():
    runtime = PaperRuntimeState()
    source = AutomatedKrakenTrader()
    source.positions.open_position("BTC/USD", _signal(), 1)
    payload = runtime.export(source, {
        "cycles": 7,
        "total_events": 7,
    })
    payload["version"] = 1
    restored = AutomatedKrakenTrader()

    evidence, did_restore = runtime.restore(restored, payload)

    assert did_restore is True
    assert restored.portfolio.has_open_position_for("BTC/USD") is True
    assert evidence["cycles"] == 0
    assert evidence["total_events"] == 0
    assert evidence["legacy_cycles"] == 7


def test_paper_runtime_rejects_unknown_version():
    evidence, restored = PaperRuntimeState().restore(
        AutomatedKrakenTrader(),
        {"version": 999},
    )

    assert restored is False
    assert evidence["cycles"] == 0
