import pandas as pd

from ml.dataset import (
    DirectionDatasetConfig,
    DirectionPredictionDatasetBuilder,
)
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


def builder(
    horizon=3,
    neutral_threshold=0.0,
):
    return DirectionPredictionDatasetBuilder(
        feature_engine=MLFeatureEngine(
            FeatureConfig(drop_warmup=False)
        ),
        config=DirectionDatasetConfig(
            horizon=horizon,
            neutral_threshold=neutral_threshold,
        ),
    )


def test_direction_dataset_aligns_future_return_to_current_row():
    candles = candle_frame(rows=40)
    dataset = builder(horizon=3).build(candles)
    first = dataset.iloc[0]
    source = candles.sort_values("timestamp").reset_index(drop=True)
    row_index = source.index[
        source["timestamp"] == first["timestamp"]
    ][0]
    expected = (
        source.loc[row_index + 3, "close"]
        / source.loc[row_index, "close"]
        - 1
    )

    assert first["future_return"] == expected
    assert first["target_direction"] == int(expected > 0)


def test_direction_dataset_drops_rows_without_future_labels():
    candles = candle_frame(rows=40)
    dataset = builder(horizon=4).build(candles)
    latest_source_timestamp = candles["timestamp"].max()

    assert dataset["timestamp"].max() < latest_source_timestamp
    assert dataset["future_return"].isna().sum() == 0


def test_direction_dataset_supports_neutral_signal_threshold():
    dataset = builder(
        horizon=2,
        neutral_threshold=0.20,
    ).build(candle_frame(rows=40))

    assert not dataset.empty
    assert set(dataset["target_signal"]) == {0}
    assert set(dataset["target_direction"]) == {0}


def test_direction_dataset_split_xy_excludes_targets_and_passthrough():
    dataset_builder = builder(horizon=3)
    dataset = dataset_builder.build(candle_frame(rows=50))
    x, y = dataset_builder.split_xy(dataset)

    assert "timestamp" not in x.columns
    assert "close" not in x.columns
    assert "future_return" not in x.columns
    assert "target_direction" not in x.columns
    assert len(x) == len(y) == len(dataset)
    assert y.name == "target_direction"


def test_direction_dataset_rejects_invalid_horizon():
    try:
        builder(horizon=0).build(candle_frame(rows=40))
    except ValueError as exc:
        assert "horizon" in str(exc)
    else:
        raise AssertionError("Expected invalid horizon error.")
