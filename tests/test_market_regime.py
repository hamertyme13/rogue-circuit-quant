import pandas as pd
import pytest

from ml.regime import MarketRegimeClassifier


def feature_frame(**overrides):
    row = {
        "timestamp": pd.Timestamp("2026-01-01"),
        "momentum_12": 0.0,
        "momentum_24": 0.0,
        "ema_fast_slow_spread": 0.0,
        "volatility_6": 0.01,
        "volatility_24": 0.01,
        "range_position_24": 0.5,
    }
    row.update(overrides)

    return pd.DataFrame([row])


def test_market_regime_classifier_detects_uptrend():
    prediction = MarketRegimeClassifier().classify_features(
        feature_frame(
            momentum_12=0.03,
            momentum_24=0.025,
            ema_fast_slow_spread=0.02,
        )
    )

    assert prediction.regime == "trend_up"
    assert prediction.confidence > 0


def test_market_regime_classifier_detects_downtrend():
    prediction = MarketRegimeClassifier().classify_features(
        feature_frame(
            momentum_12=-0.03,
            momentum_24=-0.025,
            ema_fast_slow_spread=-0.02,
        )
    )

    assert prediction.regime == "trend_down"


def test_market_regime_classifier_prioritizes_volatility_expansion():
    prediction = MarketRegimeClassifier().classify_features(
        feature_frame(
            momentum_12=0.03,
            momentum_24=0.025,
            ema_fast_slow_spread=0.02,
            volatility_6=0.03,
            volatility_24=0.01,
        )
    )

    assert prediction.regime == "volatility_expansion"
    assert prediction.volatility_ratio == pytest.approx(3.0)


def test_market_regime_classifier_detects_volatility_compression():
    prediction = MarketRegimeClassifier().classify_features(
        feature_frame(
            volatility_6=0.004,
            volatility_24=0.01,
        )
    )

    assert prediction.regime == "volatility_compression"


def test_market_regime_classifier_detects_chop():
    prediction = MarketRegimeClassifier().classify_features(
        feature_frame(
            momentum_12=0.001,
            momentum_24=-0.001,
            ema_fast_slow_spread=0.0,
            range_position_24=0.52,
        )
    )

    assert prediction.regime == "chop"


def test_market_regime_classifier_rejects_empty_features():
    with pytest.raises(ValueError):
        MarketRegimeClassifier().classify_features(pd.DataFrame())
