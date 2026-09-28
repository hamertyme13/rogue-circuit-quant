from live.shadow_validation import (
    ShadowTradingValidator,
    ShadowValidationConfig,
)


def test_shadow_validation_passes_healthy_resolved_samples():
    validator = ShadowTradingValidator(ShadowValidationConfig(min_samples=2))
    observations = [
        {
            "valid": 1,
            "cost_rate": 0.01,
            "net_return": 0.03,
            "resolved_at": "2026-01-01T00:01:00+00:00",
        },
        {
            "valid": 1,
            "cost_rate": 0.01,
            "net_return": 0.02,
            "resolved_at": "2026-01-01T00:02:00+00:00",
        },
    ]

    report = validator.evaluate(observations)

    assert report.passed is True
    assert report.valid_rate == 1.0
    assert report.profitable_rate == 1.0
    assert report.average_net_return == 0.025


def test_shadow_validation_fails_without_enough_evidence():
    report = ShadowTradingValidator().evaluate([])

    assert report.passed is False
    assert report.samples == 0
    assert any("resolved shadow samples" in reason for reason in report.reasons)


def test_shadow_validation_uses_recent_evidence_window():
    validator = ShadowTradingValidator(ShadowValidationConfig(
        min_samples=2,
        evidence_window=2,
    ))
    recent = [
        {
            "valid": 1,
            "cost_rate": 0.01,
            "net_return": 0.02,
            "resolved_at": "2026-02-01T00:00:00+00:00",
        },
        {
            "valid": 1,
            "cost_rate": 0.01,
            "net_return": 0.01,
            "resolved_at": "2026-01-31T00:00:00+00:00",
        },
    ]
    legacy = [{
        "valid": 0,
        "cost_rate": 0.0,
        "net_return": -0.5,
        "resolved_at": "2025-01-01T00:00:00+00:00",
    }]

    unresolved = [{
        "valid": 1,
        "cost_rate": 0.01,
        "net_return": None,
        "resolved_at": None,
    }]

    report = validator.evaluate(unresolved + recent + legacy)

    assert report.passed is True
    assert report.samples == 2
    assert report.valid_rate == 1.0
