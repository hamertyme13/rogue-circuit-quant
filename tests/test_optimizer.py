import pandas as pd

from optimization import optimizer as optimizer_module
from optimization.optimizer import StrategyOptimizer


def test_optimizer_evaluates_each_parameter_combination(monkeypatch):
    monkeypatch.setattr(optimizer_module, "FAST_EMAS", [5])
    monkeypatch.setattr(optimizer_module, "SLOW_EMAS", [10])
    monkeypatch.setattr(optimizer_module, "RSI_PERIODS", [6, 8])
    monkeypatch.setattr(optimizer_module, "BUY_RSI_LEVELS", [55])
    monkeypatch.setattr(optimizer_module, "SELL_RSI_LEVELS", [40, 45])

    df = pd.DataFrame({
        "timestamp": pd.date_range(
            "2026-01-01",
            periods=60,
            freq="5min",
        ),
        "open": range(60),
        "high": range(1, 61),
        "low": range(60),
        "close": range(1, 61),
        "volume": [100] * 60,
    })

    results = StrategyOptimizer().optimize(df)

    assert len(results) == 4
