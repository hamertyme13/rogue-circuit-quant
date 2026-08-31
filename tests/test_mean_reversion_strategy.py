import pandas as pd
import pytest

from models.constants import BUY, HOLD, SELL
from strategies.mean_reversion import MeanReversionStrategy


def candle_frame(closes):
    return pd.DataFrame({
        "timestamp": pd.date_range(
            "2026-01-01",
            periods=len(closes),
            freq="5min",
        ),
        "open": closes,
        "high": [value + 1 for value in closes],
        "low": [value - 1 for value in closes],
        "close": closes,
        "volume": [100] * len(closes),
    })


def test_mean_reversion_buys_oversold_move():
    closes = [100] * 20 + [90]
    signal = MeanReversionStrategy(
        window=20,
        entry_zscore=1.0,
    ).generate_signals(candle_frame(closes))[0]

    assert signal.action == BUY
    assert signal.confidence > 0
    assert signal.strategy == "MeanReversion"


def test_mean_reversion_sells_overbought_move():
    closes = [100] * 20 + [110]
    signal = MeanReversionStrategy(
        window=20,
        entry_zscore=1.0,
    ).generate_signals(candle_frame(closes))[0]

    assert signal.action == SELL


def test_mean_reversion_holds_near_mean():
    closes = [100, 101] * 12
    signal = MeanReversionStrategy(window=20).generate_signals(
        candle_frame(closes)
    )[0]

    assert signal.action == HOLD


def test_mean_reversion_rejects_invalid_window():
    with pytest.raises(ValueError):
        MeanReversionStrategy(window=1)
