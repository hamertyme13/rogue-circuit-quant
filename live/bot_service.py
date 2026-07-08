import threading


class TradingBotService:

    def __init__(
        self,
        cycle_runner,
        loop_seconds: float,
        on_success=None,
        on_error=None,
        on_stop=None,
    ):

        self.cycle_runner = cycle_runner
        self.loop_seconds = loop_seconds
        self.on_success = on_success
        self.on_error = on_error
        self.on_stop = on_stop
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

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

    def stop(self):

        self._stop_event.set()

    def is_running(self) -> bool:

        return (
            self._thread is not None
            and self._thread.is_alive()
        )

    def _run(self):

        while not self._stop_event.is_set():
            try:
                message = self.cycle_runner()
            except Exception as exc:
                if self.on_error is not None:
                    self.on_error(exc)
                break

            if self.on_success is not None:
                self.on_success(message)

            if self._stop_event.wait(self.loop_seconds):
                break

        if self.on_stop is not None:
            self.on_stop()
