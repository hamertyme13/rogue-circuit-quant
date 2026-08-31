from web_app import WebCommandCenter
import threading


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
    assert state["live_readiness"]["shadow_validation"]["passed"] is False
    assert state["shadow_observations"] == []
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
    })

    assert state["controls"]["max_order_notional"] == 300
    assert state["controls"]["min_signal_confidence"] == 0.8
    assert state["controls"]["loop_seconds"] == 5

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
    })

    assert state["daily_schedule"]["enabled"] is True
    assert state["daily_schedule"]["time"] == "07:30"
    assert state["daily_schedule"]["cycles"] == 18
    assert state["daily_schedule"]["auto_scan"] is True
    assert state["daily_schedule"]["scan_limit"] == 10
    assert state["daily_schedule"]["active_limit"] == 4
    assert center.ledger.get_setting("daily_paper_enabled") == "1"


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
