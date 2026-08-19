import pandas as pd
import pytest

from models.constants import BUY, HOLD, SELL
from strategies.breakout import BreakoutStrategy


def candle_frame(
    closes,
    highs=None,
    lows=None,
    volumes=None,
):
    highs = highs or [value + 1 for value in closes]
    lows = lows or [value - 1 for value in closes]
    volumes = volumes or [100] * len(closes)

    return pd.DataFrame({
        "timestamp": pd.date_range(
            "2026-01-01",
            periods=len(closes),
            freq="5min",
        ),
        "open": closes,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


def test_breakout_buys_new_high_with_volume_confirmation():
    closes = [100] * 20 + [105]
    highs = [102] * 20 + [106]
    volumes = [100] * 20 + [180]
    signal = BreakoutStrategy(
        lookback=20,
        volume_multiplier=1.2,
    ).generate_signals(candle_frame(closes, highs=highs, volumes=volumes))[0]

    assert signal.action == BUY
    assert signal.confidence > 0.5
    assert signal.strategy == "Breakout"


def test_breakout_sells_new_low_with_volume_confirmation():
    closes = [100] * 20 + [94]
    lows = [98] * 20 + [93]
    volumes = [100] * 20 + [180]
    signal = BreakoutStrategy(
        lookback=20,
        volume_multiplier=1.2,
    ).generate_signals(candle_frame(closes, lows=lows, volumes=volumes))[0]

    assert signal.action == SELL


def test_breakout_holds_without_volume_confirmation():
    closes = [100] * 20 + [105]
    highs = [102] * 20 + [106]
    volumes = [100] * 21
    signal = BreakoutStrategy(
        lookback=20,
        volume_multiplier=1.2,
    ).generate_signals(candle_frame(closes, highs=highs, volumes=volumes))[0]

    assert signal.action == HOLD


def test_breakout_rejects_invalid_lookback():
    with pytest.raises(ValueError):
        BreakoutStrategy(lookback=1)
