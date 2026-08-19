from web_app import WebCommandCenter


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
    state = center.record_manual_snapshot({
        "amount": 1_200,
    })

    assert state["summary"]["deposits"] == 1_000
    assert state["summary"]["current_value"] == 1_200
    assert state["summary"]["net_growth"] == 200
    assert state["snapshots"][-1]["source"] == "browser_manual"
    assert state["chart_data"]["net_growth"] == 200
    assert state["live_readiness"]["ready"] is False
    assert "paper_validation" in state["live_readiness"]
    assert state["audit_log"][0]["action"] == "manual_snapshot_recorded"
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
