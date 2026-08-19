import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class BotServiceStatus:
    running: bool
    cycles_completed: int
    errors_total: int
    consecutive_errors: int
    last_success_at: str
    last_error_at: str
    last_error: str


class TradingBotService:

    def __init__(
        self,
        cycle_runner,
        loop_seconds: float,
        on_success=None,
        on_error=None,
        on_stop=None,
        max_backoff_seconds: float = 300,
    ):

        self.cycle_runner = cycle_runner
        self.loop_seconds = loop_seconds
        self.on_success = on_success
        self.on_error = on_error
        self.on_stop = on_stop
        self.max_backoff_seconds = max_backoff_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._state_lock = threading.Lock()
        self._cycles_completed = 0
        self._errors_total = 0
        self._consecutive_errors = 0
        self._last_success_at = ""
        self._last_error_at = ""
        self._last_error = ""

    def start(self) -> bool:

        if self.is_running():
            return False

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
        )
        self._thread.start()

        return True

    def stop(self, wait: bool = False, timeout: float = 5.0):

        self._stop_event.set()

        if (
            wait
            and self._thread is not None
            and self._thread is not threading.current_thread()
        ):
            self._thread.join(timeout=timeout)

    def is_running(self) -> bool:

        return (
            self._thread is not None
            and self._thread.is_alive()
        )

    def status(self) -> dict:

        with self._state_lock:
            return asdict(BotServiceStatus(
                running=self.is_running(),
                cycles_completed=self._cycles_completed,
                errors_total=self._errors_total,
                consecutive_errors=self._consecutive_errors,
                last_success_at=self._last_success_at,
                last_error_at=self._last_error_at,
                last_error=self._last_error,
            ))

    def _run(self):

        while not self._stop_event.is_set():
            try:
                message = self.cycle_runner()
            except Exception as exc:
                with self._state_lock:
                    self._errors_total += 1
                    self._consecutive_errors += 1
                    self._last_error_at = self._now()
                    self._last_error = str(exc)
                if self.on_error is not None:
                    self.on_error(exc)

                backoff = min(
                    self.loop_seconds * (2 ** min(
                        self._consecutive_errors - 1,
                        5,
                    )),
                    self.max_backoff_seconds,
                )
                if self._stop_event.wait(backoff):
                    break
                continue

            with self._state_lock:
                self._cycles_completed += 1
                self._consecutive_errors = 0
                self._last_success_at = self._now()
                self._last_error = ""

            if self.on_success is not None:
                self.on_success(message)

            if self._stop_event.wait(self.loop_seconds):
                break

        if self.on_stop is not None:
            self.on_stop()

    @staticmethod
    def _now() -> str:

        return datetime.now(timezone.utc).isoformat()
