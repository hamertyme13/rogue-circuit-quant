from web_app import WebCommandCenter


def test_web_command_center_tracks_browser_ledger_state(tmp_path):
    center = WebCommandCenter(tmp_path / "ledger.sqlite3")

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


def test_web_command_center_settings_and_emergency_stop(tmp_path):
    center = WebCommandCenter(tmp_path / "ledger.sqlite3")

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
