from live.bot_service import TradingBotService


def test_bot_service_runs_cycle_until_stopped():
    messages = []

    def cycle():
        messages.append("ran")
        service.stop()
        return "done"

    service = TradingBotService(
        cycle_runner=cycle,
        loop_seconds=0.01,
        on_success=messages.append,
    )

    assert service.start() is True
    service._thread.join(timeout=1)

    assert messages == ["ran", "done"]
    assert service.is_running() is False


def test_bot_service_retries_after_transient_error():
    attempts = []
    errors = []

    def cycle():
        attempts.append("attempt")
        if len(attempts) == 1:
            raise RuntimeError("temporary network failure")
        service.stop()
        return "recovered"

    service = TradingBotService(
        cycle_runner=cycle,
        loop_seconds=0.01,
        max_backoff_seconds=0.01,
        on_error=errors.append,
    )

    service.start()
    service._thread.join(timeout=1)
    status = service.status()

    assert len(attempts) == 2
    assert len(errors) == 1
    assert status["cycles_completed"] == 1
    assert status["errors_total"] == 1
    assert status["consecutive_errors"] == 0
