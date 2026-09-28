from dataclasses import asdict, dataclass

from live.market_health import HEALTHY


@dataclass(frozen=True)
class LiveCandidateReport:
    symbol: str
    eligible: bool
    health_status: str
    resolved_samples: int
    valid_rate: float
    profitable_rate: float
    average_net_return: float
    reasons: tuple[str, ...]

    def as_dict(self):
        return asdict(self)


class LiveCandidateEvaluator:
    def __init__(
        self,
        min_shadow_samples: int = 5,
        min_valid_rate: float = 0.90,
        min_profitable_rate: float = 0.50,
        min_average_net_return: float = 0.0,
        evidence_window: int = 10,
    ):
        self.min_shadow_samples = int(min_shadow_samples)
        self.min_valid_rate = float(min_valid_rate)
        self.min_profitable_rate = float(min_profitable_rate)
        self.min_average_net_return = float(min_average_net_return)
        self.evidence_window = int(evidence_window)

    def evaluate(self, symbols, health_by_symbol, observations):
        rows_by_symbol = {}
        for row in observations:
            item = dict(row)
            if not item.get("resolved_at"):
                continue
            rows_by_symbol.setdefault(str(item["symbol"]), []).append(item)

        reports = []
        for symbol in dict.fromkeys(symbols):
            health = health_by_symbol.get(symbol)
            rows = rows_by_symbol.get(symbol, [])[:self.evidence_window]
            samples = len(rows)
            valid = sum(1 for row in rows if bool(row.get("valid")))
            profitable = sum(
                1 for row in rows if float(row.get("net_return") or 0.0) > 0
            )
            valid_rate = valid / samples if samples else 0.0
            profitable_rate = profitable / samples if samples else 0.0
            average_return = (
                sum(float(row.get("net_return") or 0.0) for row in rows) / samples
                if samples else 0.0
            )
            reasons = []
            health_status = health.status if health else "unrated"

            if health_status != HEALTHY:
                reasons.append("Rolling market health is not healthy.")
            if samples < self.min_shadow_samples:
                reasons.append(
                    f"Needs {self.min_shadow_samples} resolved shadow samples."
                )
            if valid_rate < self.min_valid_rate:
                reasons.append("Kraken-valid shadow rate is below target.")
            if profitable_rate < self.min_profitable_rate:
                reasons.append("Profitable shadow rate is below target.")
            if average_return < self.min_average_net_return:
                reasons.append("Average shadow return after costs is below target.")

            reports.append(LiveCandidateReport(
                symbol=symbol,
                eligible=not reasons,
                health_status=health_status,
                resolved_samples=samples,
                valid_rate=valid_rate,
                profitable_rate=profitable_rate,
                average_net_return=average_return,
                reasons=tuple(reasons),
            ))
        return reports
