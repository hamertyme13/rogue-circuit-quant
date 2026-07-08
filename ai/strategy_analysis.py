from dataclasses import dataclass

from optimization.result import OptimizationResult
from strategies.momentum import MomentumStrategy


@dataclass
class StrategyDecision:

    result: OptimizationResult
    score: float
    rationale: str

    def build_strategy(self):
        return MomentumStrategy(
            fast_ema=self.result.fast_ema,
            slow_ema=self.result.slow_ema,
            rsi_period=self.result.rsi_period,
            buy_rsi=self.result.buy_rsi,
            sell_rsi=self.result.sell_rsi,
        )


class StrategyAnalyst:

    def choose_best(
        self,
        results: list[OptimizationResult],
    ) -> StrategyDecision:

        viable = [
            result
            for result in results
            if result.trades > 0
        ]

        if not viable:
            raise ValueError(
                "No viable strategies produced trades."
            )

        ranked = sorted(
            viable,
            key=self._score,
            reverse=True,
        )

        best = ranked[0]
        score = self._score(best)

        return StrategyDecision(
            result=best,
            score=score,
            rationale=(
                "Selected for the strongest blend of net profit, "
                "win rate, trade count, and drawdown control."
            ),
        )

    def _score(self, result: OptimizationResult) -> float:

        drawdown_penalty = result.drawdown * 100
        profit_score = result.net_profit
        win_score = result.win_rate * 100
        activity_score = min(result.trades, 100)

        return (
            profit_score
            + win_score
            + activity_score
            - drawdown_penalty
        )
