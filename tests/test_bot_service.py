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
