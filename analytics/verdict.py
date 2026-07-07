from dataclasses import dataclass


@dataclass
class Verdict:

    passed: bool

    score: int

    reasons: list[str]

class VerdictEngine:

    def evaluate(self, metrics):

        score = 100

        reasons = []

        if metrics.total_profit() <= 0:

            score -= 35

            reasons.append(
                "Negative profit"
            )

        if metrics.win_rate() < 0.50:

            score -= 25

            reasons.append(
                "Win rate below 50%"
            )

        if metrics.max_drawdown() > 0.10:

            score -= 20

            reasons.append(
                "Drawdown above 10%"
            )

        if metrics.total_trades() < 10:

            score -= 20

            reasons.append(
                "Sample size too small"
            )

        return Verdict(

            passed=score >= 70,

            score=max(score, 0),

            reasons=reasons,
        )