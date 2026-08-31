from datetime import datetime

from live.daily_scheduler import DailyPaperScheduler


def test_daily_scheduler_runs_once_after_local_start_time():
    calls = []
    settings = {
        "enabled": True,
        "time": "09:00",
        "cycles": 12,
        "last_run_date": "",
    }

    def run_session(cycles, run_date):
        calls.append((cycles, run_date))
        settings["last_run_date"] = run_date
        return "started"

    scheduler = DailyPaperScheduler(run_session, lambda: settings)
    now = datetime.fromisoformat("2026-08-24T09:05:00-04:00")

    assert scheduler.tick(now) is True
    assert scheduler.tick(now) is False
    assert calls == [(12, "2026-08-24")]


def test_daily_scheduler_waits_until_start_time():
    settings = {
        "enabled": True,
        "time": "09:00",
        "cycles": 12,
        "last_run_date": "",
    }
    scheduler = DailyPaperScheduler(lambda *_: "started", lambda: settings)

    assert scheduler.tick(
        datetime.fromisoformat("2026-08-24T08:59:00-04:00")
    ) is False
