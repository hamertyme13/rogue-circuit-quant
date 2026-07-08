from ai.strategy_analysis import StrategyAnalyst
from optimization.result import OptimizationResult


def test_strategy_analyst_prefers_profit_with_drawdown_control():
    analyst = StrategyAnalyst()

    weak = OptimizationResult(
        fast_ema=10,
        slow_ema=30,
        rsi_period=14,
        buy_rsi=55,
        sell_rsi=45,
        trades=5,
        win_rate=0.4,
        net_profit=10,
        drawdown=0.20,
    )
    strong = OptimizationResult(
        fast_ema=15,
        slow_ema=40,
        rsi_period=14,
        buy_rsi=60,
        sell_rsi=40,
        trades=12,
        win_rate=0.6,
        net_profit=100,
        drawdown=0.05,
    )

    decision = analyst.choose_best([weak, strong])

    assert decision.result == strong


def test_strategy_analyst_rejects_empty_results():
    analyst = StrategyAnalyst()

    try:
        analyst.choose_best([])
    except ValueError as exc:
        assert "No viable strategies" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
