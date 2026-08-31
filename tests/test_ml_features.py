import pandas as pd

from ml.features import FeatureConfig, MLFeatureEngine


def candle_frame(rows=80):
    timestamps = pd.date_range(
        "2026-01-01",
        periods=rows,
        freq="5min",
    )
    close = pd.Series(
        [100 + index * 0.5 + (index % 5) for index in range(rows)],
        dtype=float,
    )

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": close - 0.3,
        "high": close + 1.2,
        "low": close - 1.1,
        "close": close,
        "volume": [
            10 + (index % 7) * 2
            for index in range(rows)
        ],
    })


def test_feature_engine_builds_ml_ready_features():
    engine = MLFeatureEngine()

    features = engine.build(candle_frame())
    feature_columns = engine.feature_columns(features)

    assert not features.empty
    assert features.isna().sum().sum() == 0
    assert "return_3" in feature_columns
    assert "ema_21_distance" in feature_columns
    assert "rsi_14" in feature_columns
    assert "volume_zscore_24" in feature_columns
    assert "minute_sin" in feature_columns
    assert "timestamp" not in feature_columns


def test_feature_engine_does_not_leak_future_rows():
    engine = MLFeatureEngine(
        FeatureConfig(drop_warmup=False)
    )
    candles = candle_frame()
    changed = candles.copy()
    changed.loc[changed.index[-1], "close"] *= 2

    baseline = engine.build(candles).iloc[:-1].reset_index(drop=True)
    variant = engine.build(changed).iloc[:-1].reset_index(drop=True)

    pd.testing.assert_frame_equal(
        baseline,
        variant,
    )


def test_feature_engine_validates_required_columns():
    engine = MLFeatureEngine()
    candles = candle_frame().drop(columns=["volume"])

    try:
        engine.build(candles)
    except ValueError as exc:
        assert "volume" in str(exc)
    else:
        raise AssertionError("Expected missing column validation error.")
