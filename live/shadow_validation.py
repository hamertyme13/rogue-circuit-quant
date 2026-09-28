from dataclasses import dataclass, field


@dataclass(frozen=True)
class ShadowValidationConfig:
    min_samples: int = 25
    evidence_window: int = 25
    min_valid_rate: float = 0.90
    min_profitable_rate: float = 0.50
    max_cost_rate: float = 0.02
    min_average_net_return: float = 0.0


@dataclass(frozen=True)
class ShadowValidationReport:
    samples: int
    resolved_samples: int
    valid_samples: int
    profitable_samples: int
    valid_rate: float
    profitable_rate: float
    average_cost_rate: float
    average_net_return: float
    passed: bool
    reasons: list[str] = field(default_factory=list)


class ShadowTradingValidator:
    def __init__(self, config: ShadowValidationConfig | None = None):
        self.config = config or ShadowValidationConfig()

    def evaluate(self, observations) -> ShadowValidationReport:
        rows = [dict(row) for row in observations]
        resolved = [
            row for row in rows if row.get("resolved_at")
        ][:self.config.evidence_window]
        rows = resolved
        valid = [row for row in resolved if bool(row.get("valid"))]
        profitable = [
            row for row in resolved
            if float(row.get("net_return") or 0.0) > 0
        ]
        samples = len(rows)
        resolved_samples = len(resolved)
        valid_rate = len(valid) / samples if samples else 0.0
        profitable_rate = (
            len(profitable) / resolved_samples if resolved_samples else 0.0
        )
        average_cost_rate = self._average(rows, "cost_rate")
        average_net_return = self._average(resolved, "net_return")
        reasons = []

        if resolved_samples < self.config.min_samples:
            reasons.append(
                f"Needs at least {self.config.min_samples} resolved shadow samples."
            )
        if valid_rate < self.config.min_valid_rate:
            reasons.append("Kraken-valid shadow order rate is below target.")
        if profitable_rate < self.config.min_profitable_rate:
            reasons.append("Profitable shadow outcome rate is below target.")
        if average_cost_rate > self.config.max_cost_rate:
            reasons.append("Estimated fee and slippage rate is above target.")
        if average_net_return < self.config.min_average_net_return:
            reasons.append("Average shadow return after costs is below target.")

        return ShadowValidationReport(
            samples=samples,
            resolved_samples=resolved_samples,
            valid_samples=len(valid),
            profitable_samples=len(profitable),
            valid_rate=valid_rate,
            profitable_rate=profitable_rate,
            average_cost_rate=average_cost_rate,
            average_net_return=average_net_return,
            passed=not reasons,
            reasons=reasons,
        )

    @staticmethod
    def _average(rows, key):
        values = [float(row.get(key) or 0.0) for row in rows]
        return sum(values) / len(values) if values else 0.0
