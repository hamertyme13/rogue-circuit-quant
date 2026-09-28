from web_app import WebCommandCenter
import threading

from live.trader import TradeCycleEvent


def test_web_command_center_tracks_browser_ledger_state(tmp_path):
    center = WebCommandCenter(
        tmp_path / "ledger.sqlite3",
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )

    state = center.add_deposit({
        "amount": 1_000,
        "note": "initial",
    })
    center.ledger.record_snapshot(
        total_value=1_200,
        cash_value=200,
        positions_value=1_000,
        source="kraken",
    )
    state = center.state()

    assert state["summary"]["deposits"] == 1_000
    assert state["summary"]["current_value"] == 1_200
    assert state["summary"]["net_growth"] == 200
    assert state["snapshots"][-1]["source"] == "kraken"
    assert state["chart_data"]["net_growth"] == 200
    assert state["live_readiness"]["ready"] is False
    assert "paper_validation" in state["live_readiness"]
    assert "shadow_validation" in state["live_readiness"]
    assert "candidate_validation" in state["live_readiness"]
    assert state["live_readiness"]["eligible_candidate_count"] == 0
    assert "live_candidates" in state
    assert state["live_readiness"]["shadow_validation"]["passed"] is False
    assert state["shadow_observations"] == []
    assert state["market_health"] == []
    assert state["audit_log"][0]["action"] == "deposit_added"
    assert state["deployment_mode"]["name"] in {
        "local",
        "paper",
        "live_locked",
        "live_enabled",
        "maintenance",
    }


def test_web_command_center_settings_and_emergency_stop(tmp_path):
    center = WebCommandCenter(
        tmp_path / "ledger.sqlite3",
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )

    state = center.apply_settings({
        "max_order_notional": 300,
        "min_signal_confidence": 0.8,
        "loop_seconds": 5,
        "max_open_positions": 4,
        "max_portfolio_exposure": 0.4,
        "max_asset_exposure": 0.12,
        "min_cash_reserve": 0.25,
    })

    assert state["controls"]["max_order_notional"] == 300
    assert state["controls"]["min_signal_confidence"] == 0.8
    assert state["controls"]["loop_seconds"] == 5
    assert state["allocation"]["max_open_positions"] == 4
    assert state["allocation"]["max_portfolio_exposure"] == 0.4
    assert state["allocation"]["max_asset_exposure"] == 0.12
    assert state["allocation"]["min_cash_reserve"] == 0.25

    state = center.emergency_stop()

    assert state["service"]["emergency_stop"] is True
    assert state["audit_log"][0]["action"] == "emergency_stop"


def test_web_command_center_stores_credentials_without_exposing_them(
    tmp_path,
):
    center = WebCommandCenter(
        tmp_path / "ledger.sqlite3",
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )

    state = center.store_credentials({
        "api_key": "key-value",
        "api_secret": "secret-value",
    })

    raw = (tmp_path / "vault.json").read_text(encoding="utf-8")

    assert "secret-value" not in raw
    assert state["credential_status"]["kraken_configured"] is True
    assert state["live_readiness"]["credentials_configured"] is True
    assert "secret-value" not in str(state)


def test_web_command_center_live_readiness_explains_locked_state(tmp_path):
    center = WebCommandCenter(
        tmp_path / "ledger.sqlite3",
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )

    readiness = center.state()["live_readiness"]

    assert readiness["ready"] is False
    assert readiness["deployment_allows_live"] is False
    assert readiness["paper_validation"]["cycles"] == 0
    assert readiness["paper_validation"]["passed"] is False
    assert any(
        "Deployment mode" in reason
        for reason in readiness["reasons"]
    )


def test_web_command_center_persists_shadow_mode(tmp_path):
    center = WebCommandCenter(
        tmp_path / "ledger.sqlite3",
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )
    center.credential_vault.store_kraken_credentials("key", "secret")

    state = center.set_execution_mode({"mode": "shadow"})

    assert state["execution_safety"]["mode"] == "shadow"
    assert center.ledger.get_setting("execution_mode", "") == "shadow"


def test_web_command_center_persists_daily_paper_schedule(tmp_path):
    center = WebCommandCenter(
        tmp_path / "ledger.sqlite3",
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )

    state = center.apply_daily_schedule({
        "enabled": True,
        "time": "07:30",
        "cycles": 18,
        "auto_scan": True,
        "scan_limit": 10,
        "active_limit": 4,
        "auto_shadow": True,
        "shadow_cycles": 5,
    })

    assert state["daily_schedule"]["enabled"] is True
    assert state["daily_schedule"]["time"] == "07:30"
    assert state["daily_schedule"]["cycles"] == 18
    assert state["daily_schedule"]["auto_scan"] is True
    assert state["daily_schedule"]["scan_limit"] == 10
    assert state["daily_schedule"]["active_limit"] == 4
    assert state["daily_schedule"]["auto_shadow"] is True
    assert state["daily_schedule"]["shadow_cycles"] == 5
    assert center.ledger.get_setting("daily_paper_enabled") == "1"
    assert center.ledger.get_setting("daily_auto_shadow") == "1"
    assert center.ledger.get_setting("daily_shadow_cycles") == "5"


def test_completed_daily_paper_session_schedules_shadow_followup(tmp_path):
    center = WebCommandCenter(
        tmp_path / "ledger.sqlite3",
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )
    scheduled = []
    center._scheduled_session_phase = "paper"
    center.ledger.set_setting("pending_shadow_cycles", 4)
    center._schedule_shadow_followup = scheduled.append

    center._service_stopped()

    assert scheduled == [4]
    assert center._scheduled_session_phase == ""


def test_shadow_followup_runs_without_orders_then_returns_to_paper(tmp_path):
    center = WebCommandCenter(
        tmp_path / "ledger.sqlite3",
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )
    center.credential_vault.store_kraken_credentials("key", "secret")

    class FakeService:
        def __init__(self):
            self.started_cycles = None

        def is_running(self):
            return False

        def start(self, max_cycles=None):
            self.started_cycles = max_cycles
            return True

    service = FakeService()
    center.service = service

    center._start_shadow_followup(3)

    assert service.started_cycles == 3
    assert center.trader.execution_mode == "shadow"
    assert center._scheduled_session_phase == "shadow"

    center._service_stopped()

    assert center.trader.execution_mode == "paper"
    assert center.ledger.get_setting("pending_shadow_cycles") == "0"


def test_shadow_followup_skips_without_credentials(tmp_path):
    center = WebCommandCenter(
        tmp_path / "ledger.sqlite3",
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )
    center.ledger.set_setting("pending_shadow_cycles", 3)

    center._start_shadow_followup(3)

    assert center.trader.execution_mode == "paper"
    assert center.ledger.get_setting("pending_shadow_cycles") == "0"
    assert "credentials missing" in center.ledger.alerts(limit=1)[0]["message"]


def test_stop_during_scheduled_scan_prevents_bot_start(tmp_path):
    center = WebCommandCenter(
        tmp_path / "ledger.sqlite3",
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )
    center.ledger.set_setting("daily_paper_auto_scan", 1)
    started = []
    center.service.start = lambda max_cycles=None: started.append(max_cycles) or True

    def scan_then_stop(*_):
        center.stop_service()
        return [], ["BTC/USD"]

    center._perform_market_scan = scan_then_stop

    result = center._start_daily_paper_session(12, "2026-09-27")

    assert "stopped" in result
    assert started == []
    assert center.ledger.get_setting("pending_shadow_cycles", "0") == "0"


def test_market_cycle_does_not_block_dashboard_state(tmp_path):
    center = WebCommandCenter(
        tmp_path / "ledger.sqlite3",
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )
    entered = threading.Event()
    release = threading.Event()

    def slow_cycle():
        entered.set()
        release.wait(timeout=1)
        return []

    center.trader.run_once = slow_cycle
    worker = threading.Thread(target=center.run_one_cycle)
    worker.start()
    assert entered.wait(timeout=1)

    state = center.state()
    release.set()
    worker.join(timeout=1)

    assert state["service"]["running"] is False
    assert worker.is_alive() is False


def test_web_command_center_restores_paper_runtime(tmp_path):
    ledger_path = tmp_path / "ledger.sqlite3"
    center = WebCommandCenter(
        ledger_path,
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )
    center.trader.portfolio.cash = 9_500
    center.trader.cycles = 7
    center.paper_evidence.update({
        "cycles": 6,
        "total_events": 18,
        "executed_events": 3,
        "opportunity_events": 5,
    })
    center._save_paper_runtime()

    restored = WebCommandCenter(
        ledger_path,
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )
    state = restored.state()

    assert state["paper_runtime"]["restored"] is True
    assert state["paper_runtime"]["cycles"] == 6
    assert restored.trader.portfolio.cash == 9_500
    assert state["live_readiness"]["paper_validation"]["cycles"] == 6


def test_paper_readiness_counts_only_complete_fresh_market_cycles(tmp_path):
    ledger_path = tmp_path / "ledger.sqlite3"
    center = WebCommandCenter(
        ledger_path,
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )
    center.trader.symbols = ["BTC/USD", "ETH/USD"]
    healthy = TradeCycleEvent(
        symbol="BTC/USD",
        action="HOLD",
        confidence=0.0,
        price=100.0,
        strategy="Momentum",
        executed=False,
        mode="paper",
    )
    failed = TradeCycleEvent(
        symbol="ETH/USD",
        action="HOLD",
        confidence=0.0,
        price=0.0,
        strategy="MarketError",
        executed=False,
        mode="paper",
    )
    center.trader.run_once = lambda: [healthy, failed]

    center.run_one_cycle()

    assert center.paper_evidence["cycles"] == 0
    assert center.paper_evidence["unverified_cycles"] == 1
    assert len(center.ledger.decisions()) == 2

    center.trader.run_once = lambda: [healthy, TradeCycleEvent(
        symbol="ETH/USD",
        action="HOLD",
        confidence=0.0,
        price=200.0,
        strategy="Momentum",
        executed=False,
        mode="paper",
    )]
    center.run_one_cycle()

    assert center.paper_evidence["cycles"] == 1
    assert center.paper_evidence["total_events"] == 2
    assert center.paper_evidence["unverified_cycles"] == 1
    restored = WebCommandCenter(
        ledger_path,
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )
    assert restored.paper_evidence["cycles"] == 1
    assert restored.paper_evidence["unverified_cycles"] == 1


def test_shadow_cycle_records_actionable_buy_without_opportunity_label(tmp_path):
    center = WebCommandCenter(
        tmp_path / "ledger.sqlite3",
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )
    center.trader.set_execution_mode("shadow")
    center.trader.last_order_previews["BTC/USD"] = {
        "valid": True,
        "notional": 5.0,
        "estimated_fee": 0.04,
        "estimated_slippage": 0.01,
    }
    center.trader.run_once = lambda: [TradeCycleEvent(
        symbol="BTC/USD",
        action="BUY",
        confidence=0.8,
        price=50_000,
        strategy="Momentum",
        executed=False,
        quantity=0.0001,
        reason="Shadow BUY validated; no Kraken order sent.",
        order_id="ca-test",
        order_status="validated",
        mode="shadow",
        opportunity=False,
    )]

    center.run_one_cycle()

    rows = center.ledger.shadow_observations()
    assert len(rows) == 1
    assert rows[0]["symbol"] == "BTC/USD"
    assert rows[0]["valid"] == 1
    assert rows[0]["cost_rate"] == 0.01


def test_shadow_hold_does_not_record_stale_order_preview(tmp_path):
    center = WebCommandCenter(
        tmp_path / "ledger.sqlite3",
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )
    center.trader.set_execution_mode("shadow")
    center.trader.last_order_previews["BTC/USD"] = {"valid": True}
    center.trader.run_once = lambda: [TradeCycleEvent(
        symbol="BTC/USD",
        action="HOLD",
        confidence=0.0,
        price=50_000,
        strategy="Momentum",
        executed=False,
        mode="shadow",
    )]

    center.run_one_cycle()

    assert center.ledger.shadow_observations() == []


def test_dashboard_reads_resolved_shadow_rows_from_sqlite(tmp_path):
    center = WebCommandCenter(
        tmp_path / "ledger.sqlite3",
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )
    center.ledger.record_shadow_observation(
        symbol="BTC/USD",
        action="BUY",
        strategy="Momentum",
        confidence=0.8,
        entry_price=100,
        quantity=0.05,
        valid=True,
        cost_rate=0.01,
    )
    center.ledger.resolve_shadow_observations("BTC/USD", 102)

    state = center.state()

    assert state["live_readiness"]["shadow_validation"]["resolved_samples"] == 1
