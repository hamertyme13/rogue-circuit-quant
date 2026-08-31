import threading
from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True)
class DailyScheduleStatus:
    enabled: bool
    time: str
    cycles: int
    auto_scan: bool
    scan_limit: int
    active_limit: int
    last_run_date: str
    last_started_at: str
    last_result: str
    next_run: str


class DailyPaperScheduler:
    def __init__(self, run_session, settings_loader, poll_seconds=30.0):
        self.run_session = run_session
        self.settings_loader = settings_loader
        self.poll_seconds = float(poll_seconds)
        self._stop_event = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._last_started_at = ""
        self._last_result = "Waiting for the next scheduled paper session."

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return False
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop_event.set()

    def tick(self, now=None):
        now = now or datetime.now().astimezone()
        settings = self.settings_loader()
        if not settings["enabled"]:
            return False
        run_date = now.date().isoformat()
        if settings["last_run_date"] == run_date:
            return False
        hour, minute = (int(value) for value in settings["time"].split(":"))
        if (now.hour, now.minute) < (hour, minute):
            return False

        with self._lock:
            self._last_started_at = now.isoformat()
        result = self.run_session(settings["cycles"], run_date)
        with self._lock:
            self._last_result = str(result)
        return True

    def status(self, now=None):
        now = now or datetime.now().astimezone()
        settings = self.settings_loader()
        hour, minute = (int(value) for value in settings["time"].split(":"))
        next_day = now.date()
        if settings["last_run_date"] == next_day.isoformat():
            next_day = next_day.fromordinal(next_day.toordinal() + 1)
        next_run = datetime.combine(
            next_day,
            datetime.min.time().replace(hour=hour, minute=minute),
            tzinfo=now.tzinfo,
        ).isoformat()
        with self._lock:
            return asdict(DailyScheduleStatus(
                enabled=settings["enabled"],
                time=settings["time"],
                cycles=settings["cycles"],
                auto_scan=settings.get("auto_scan", True),
                scan_limit=settings.get("scan_limit", 8),
                active_limit=settings.get("active_limit", 3),
                last_run_date=settings["last_run_date"],
                last_started_at=self._last_started_at,
                last_result=self._last_result,
                next_run=next_run,
            ))

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self.tick()
            except Exception as exc:
                with self._lock:
                    self._last_result = f"Daily schedule error: {exc}"
            self._stop_event.wait(self.poll_seconds)
