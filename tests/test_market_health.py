from live.market_health import (
    HEALTHY,
    LEARNING,
    QUARANTINED,
    MarketHealthEngine,
)


def _shadow(symbol, value):
    return {
        "symbol": symbol,
        "net_return": value,
        "resolved_at": "2026-09-01T00:00:00+00:00",
    }


def test_market_health_quarantines_repeated_weak_outcomes():
    profiles = MarketHealthEngine(min_samples=5).evaluate(
        [_shadow("BTC/USD", value) for value in [-0.03, -0.02, 0.01, -0.01]],
        [{"symbol": "BTC/USD", "pnl": -2.0}],
    )

    profile = profiles["BTC/USD"]
    assert profile.status == QUARANTINED
    assert profile.samples == 5
    assert profile.win_rate == 0.2
    assert profile.average_shadow_return < 0


def test_market_health_promotes_consistent_market():
    profiles = MarketHealthEngine(min_samples=5).evaluate(
        [_shadow("ETH/USD", value) for value in [0.03, 0.02, -0.01, 0.01]],
        [{"symbol": "ETH/USD", "pnl": 4.0}],
    )

    assert profiles["ETH/USD"].status == HEALTHY
    assert profiles["ETH/USD"].win_rate == 0.8


def test_market_health_keeps_small_sample_in_learning():
    profiles = MarketHealthEngine(min_samples=5).evaluate(
        [_shadow("SOL/USD", 0.05)],
        [],
    )

    assert profiles["SOL/USD"].status == LEARNING
