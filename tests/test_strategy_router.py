import pandas as pd

from ml.regime import MarketRegimePrediction
from models.constants import BUY, HOLD
from models.signal import Signal
from strategies.base import Strategy
from strategies.router import (
    AIStrategyRouter,
    StrategyHealth,
    StrategyRouterConfig,
)


class StaticRegimeClassifier:

    def __init__(
        self,
        regime,
        confidence=0.8,
    ):

        self.prediction = MarketRegimePrediction(
            regime=regime,
            confidence=confidence,
            trend_score=0.02,
            volatility_ratio=1.0,
            range_position=0.5,
        )

    def classify_candles(
        self,
        candles,
    ):

        return self.prediction


class StaticStrategy(Strategy):

    def __init__(
        self,
        name,
    ):

        self.name = name

    def generate_signals(
        self,
        df,
    ):

        latest = df.iloc[-1]

        return [
            Signal(
                timestamp=latest["timestamp"],
                action=BUY,
                price=float(latest["close"]),
                confidence=0.8,
                strategy=self.name,
            )
        ]


class BlockingRiskManager:

    def can_open_trade(self):

        return False


def candle_frame():
    return pd.DataFrame({
        "timestamp": pd.date_range(
            "2026-01-01",
            periods=30,
            freq="5min",
        ),
        "open": range(30),
        "high": range(1, 31),
        "low": range(30),
        "close": range(1, 31),
        "volume": [100] * 30,
    })


def strategies():
    return {
        "momentum": StaticStrategy("Momentum"),
        "mean_reversion": StaticStrategy("MeanReversion"),
        "breakout": StaticStrategy("Breakout"),
    }


def test_strategy_router_selects_momentum_for_trend():
    router = AIStrategyRouter(
        strategies=strategies(),
        regime_classifier=StaticRegimeClassifier("trend_up"),
    )

    signal = router.generate_signals(candle_frame())[0]

    assert signal.action == BUY
    assert signal.strategy.startswith("Router:momentum:trend_up")


def test_strategy_router_selects_mean_reversion_for_chop():
    router = AIStrategyRouter(
        strategies=strategies(),
        regime_classifier=StaticRegimeClassifier("chop"),
    )

    signal = router.generate_signals(candle_frame())[0]

    assert signal.strategy.startswith("Router:mean_reversion:chop")


def test_strategy_router_selects_breakout_for_volatility_expansion():
    router = AIStrategyRouter(
        strategies=strategies(),
        regime_classifier=StaticRegimeClassifier("volatility_expansion"),
    )

    signal = router.generate_signals(candle_frame())[0]

    assert signal.strategy.startswith("Router:breakout:volatility_expansion")


def test_strategy_router_skips_unhealthy_candidate():
    router = AIStrategyRouter(
        strategies=strategies(),
        regime_classifier=StaticRegimeClassifier("volatility_expansion"),
        config=StrategyRouterConfig(min_strategy_score=0.5),
        strategy_health={
            "breakout": StrategyHealth(
                name="breakout",
                score=0.2,
            )
        },
    )

    signal = router.generate_signals(candle_frame())[0]

    assert signal.strategy.startswith("Router:momentum")


def test_strategy_router_respects_risk_manager():
    router = AIStrategyRouter(
        strategies=strategies(),
        regime_classifier=StaticRegimeClassifier("trend_up"),
        risk_manager=BlockingRiskManager(),
    )

    signal = router.generate_signals(candle_frame())[0]

    assert signal.action == HOLD
    assert signal.strategy == "RouterRisk"
