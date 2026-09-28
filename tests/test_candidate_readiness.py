from live.candidate_readiness import LiveCandidateEvaluator
from live.market_health import MarketHealthProfile


def _health(symbol, status="healthy"):
    return MarketHealthProfile(
        symbol=symbol,
        status=status,
        samples=8,
        wins=6,
        win_rate=0.75,
        average_shadow_return=0.02,
        paper_pnl=10.0,
        reason="Test evidence.",
    )


def _observation(symbol, value=0.02, valid=1):
    return {
        "symbol": symbol,
        "valid": valid,
        "net_return": value,
        "resolved_at": "2026-09-01T00:00:00+00:00",
    }


def test_candidate_passes_with_healthy_profitable_shadow_evidence():
    rows = [
        _observation("BTC/USD", value)
        for value in (0.03, 0.02, 0.01, -0.01, 0.02)
    ]
    report = LiveCandidateEvaluator().evaluate(
        ["BTC/USD"],
        {"BTC/USD": _health("BTC/USD")},
        rows,
    )[0]

    assert report.eligible is True
    assert report.resolved_samples == 5
    assert report.valid_rate == 1.0
    assert report.profitable_rate == 0.8


def test_candidate_fails_when_market_is_unhealthy_or_samples_are_sparse():
    report = LiveCandidateEvaluator().evaluate(
        ["SOL/USD"],
        {"SOL/USD": _health("SOL/USD", "quarantined")},
        [_observation("SOL/USD")],
    )[0]

    assert report.eligible is False
    assert any("not healthy" in reason for reason in report.reasons)
    assert any("5 resolved" in reason for reason in report.reasons)


def test_candidate_uses_recent_market_evidence_window():
    recent = [_observation("BTC/USD", 0.02) for _ in range(5)]
    legacy = [_observation("BTC/USD", -0.20, valid=0) for _ in range(5)]

    report = LiveCandidateEvaluator(evidence_window=5).evaluate(
        ["BTC/USD"],
        {"BTC/USD": _health("BTC/USD")},
        recent + legacy,
    )[0]

    assert report.eligible is True
    assert report.resolved_samples == 5
    assert report.valid_rate == 1.0
