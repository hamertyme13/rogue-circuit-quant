import sqlite3

from accounting.ledger import InvestmentLedger
from live.shadow_validation import ShadowTradingValidator, ShadowValidationConfig


def test_ledger_tracks_net_deposits_and_growth(tmp_path):
    ledger = InvestmentLedger(tmp_path / "ledger.sqlite3")

    ledger.add_deposit(1_000)
    ledger.add_deposit(500)
    ledger.add_withdrawal(200)
    ledger.record_snapshot(
        total_value=1_600,
        cash_value=400,
        positions_value=1_200,
        source="test",
    )

    summary = ledger.summary()

    assert summary.deposits == 1_500
    assert summary.withdrawals == 200
    assert summary.net_deposits == 1_300
    assert summary.current_value == 1_600
    assert summary.net_growth == 300
    assert summary.growth_percent == 300 / 1_300


def test_ledger_uses_net_deposits_when_no_snapshot_exists(tmp_path):
    ledger = InvestmentLedger(tmp_path / "ledger.sqlite3")

    ledger.add_deposit(1_000)
    ledger.add_withdrawal(250)

    summary = ledger.summary()

    assert summary.current_value == 750
    assert summary.net_growth == 0


def test_ledger_can_exclude_paper_equity_from_real_account_value(tmp_path):
    ledger = InvestmentLedger(tmp_path / "ledger.sqlite3")
    ledger.add_deposit(10)
    ledger.record_snapshot(8.5, source="kraken")
    ledger.record_snapshot(10_000, source="browser_paper_trader")

    summary = ledger.summary(snapshot_sources=("kraken",))
    snapshots = ledger.snapshots(sources=("kraken",))

    assert summary.current_value == 8.5
    assert summary.net_growth == -1.5
    assert [snapshot.total_value for snapshot in snapshots] == [8.5]


def test_ledger_records_decisions_strategy_performance_alerts_and_settings(
    tmp_path,
):
    ledger = InvestmentLedger(tmp_path / "ledger.sqlite3")

    ledger.record_decision(
        symbol="BTC/USD",
        strategy="Momentum",
        action="BUY",
        confidence=0.82,
        price=50_000,
        executed=True,
        quantity=0.01,
        reason="Paper buy opened.",
        mode="paper",
    )
    ledger.record_strategy_performance(
        symbol="BTC/USD",
        strategy="Momentum",
        score=123.4,
        net_profit=42,
        win_rate=0.6,
        drawdown=0.05,
        trades=12,
        rationale="Best risk-adjusted candidate.",
    )
    ledger.add_alert(
        "INFO",
        "Bot service started.",
        "test",
    )
    ledger.set_setting("max_order_notional", 250)
    ledger.set_emergency_stop(True)

    decision = ledger.decisions()[0]
    performance = ledger.strategy_performance()[0]
    alert = ledger.alerts()[0]
    controls = ledger.bot_controls(
        max_order_notional=100,
        min_signal_confidence=0.7,
        loop_seconds=60,
    )

    assert decision["symbol"] == "BTC/USD"
    assert decision["executed"] == 1
    assert performance["score"] == 123.4
    assert alert["level"] == "INFO"
    assert controls.max_order_notional == 250
    assert controls.emergency_stop is True


def test_ledger_records_audit_and_paper_live_comparison(tmp_path):
    ledger = InvestmentLedger(tmp_path / "ledger.sqlite3")

    ledger.record_audit_event(
        actor="tester",
        action="settings_saved",
        detail="Risk controls updated.",
        source="unit",
    )
    ledger.record_paper_live_comparison(
        symbol="BTC/USD",
        paper_action="BUY",
        live_action="LOCKED",
        paper_price=50_000,
        live_price=50_000,
        difference=0,
        reason="Deployment mode locked live trading.",
    )

    audit = ledger.audit_log()[0]
    comparison = ledger.paper_live_comparisons()[0]

    assert audit["actor"] == "tester"
    assert audit["action"] == "settings_saved"
    assert comparison["symbol"] == "BTC/USD"
    assert comparison["live_action"] == "LOCKED"


def test_ledger_resolves_shadow_observation_after_costs(tmp_path):
    ledger = InvestmentLedger(tmp_path / "ledger.sqlite3")
    ledger.record_shadow_observation(
        symbol="BTC/USD",
        action="BUY",
        strategy="Momentum",
        confidence=0.8,
        entry_price=100.0,
        quantity=1.0,
        valid=True,
        cost_rate=0.01,
        preview_version=2,
    )

    assert ledger.resolve_shadow_observations("BTC/USD", 105.0) == 1
    observation = ledger.shadow_observations()[0]

    assert observation["exit_price"] == 105.0
    assert round(observation["gross_return"], 6) == 0.05
    assert round(observation["net_return"], 6) == 0.04
    assert observation["resolved_at"] is not None
    assert observation["preview_version"] == 2


def test_legacy_shadow_rows_remain_visible_but_do_not_pass_new_gate(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE shadow_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL, action TEXT NOT NULL,
                strategy TEXT NOT NULL, confidence REAL NOT NULL,
                entry_price REAL NOT NULL, exit_price REAL,
                quantity REAL NOT NULL, valid INTEGER NOT NULL,
                cost_rate REAL NOT NULL, gross_return REAL,
                net_return REAL, reason TEXT NOT NULL,
                created_at TEXT NOT NULL, resolved_at TEXT
            )
        """)
        conn.execute("""
            INSERT INTO shadow_observations (
                symbol, action, strategy, confidence, entry_price,
                quantity, valid, cost_rate, net_return, reason,
                created_at, resolved_at
            ) VALUES ('BTC/USD','BUY','Momentum',0.8,100,0,0,0,0.05,
                'Risk controls blocked the buy.','2026-08-01','2026-08-02')
        """)

    ledger = InvestmentLedger(path)
    rows = ledger.shadow_observations()
    report = ShadowTradingValidator(
        ShadowValidationConfig(min_samples=1)
    ).evaluate(rows)
    assert len(rows) == 1
    assert rows[0]["preview_version"] == 0
    assert report.resolved_samples == 0
    assert report.passed is False

    ledger.record_shadow_observation(
        symbol="BTC/USD", action="BUY", strategy="Momentum",
        confidence=0.8, entry_price=100, quantity=0.05,
        valid=True, cost_rate=0.01,
        preview_version=2,
    )
    ledger.resolve_shadow_observations("BTC/USD", 102)
    rows = ledger.shadow_observations()
    assert [row["preview_version"] for row in rows] == [2, 0]
    assert ShadowTradingValidator(
        ShadowValidationConfig(min_samples=1)
    ).evaluate(rows).resolved_samples == 1


def test_live_order_journal_survives_restart_and_mode_change(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    ledger = InvestmentLedger(path)
    ledger.begin_live_order("session-a", "ca-1", "BTC/USD", "buy", 0.01, 2)
    assert "unresolved" in ledger.live_order_block_reason("session-a", 2)

    reopened = InvestmentLedger(path)
    assert "unresolved" in reopened.live_order_block_reason("session-b", 2)
    reopened.update_live_order("ca-1", "observed", "kraken-order-1")
    assert reopened.live_order_intents()[0]["order_id"] == "kraken-order-1"
    assert "prior-session" in reopened.live_order_block_reason("session-b", 2)

    reopened.begin_live_order("session-a", "ca-2", "BTC/USD", "sell", 0.01, 2)
    reopened.update_live_order("ca-2", "observed", "kraken-order-2")
    assert "session order limit" in reopened.live_order_block_reason("session-a", 2)
