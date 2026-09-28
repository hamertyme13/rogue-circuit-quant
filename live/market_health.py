from dataclasses import asdict, dataclass


LEARNING = "learning"
HEALTHY = "healthy"
QUARANTINED = "quarantined"


@dataclass(frozen=True)
class MarketHealthProfile:
    symbol: str
    status: str
    samples: int
    wins: int
    win_rate: float
    average_shadow_return: float
    paper_pnl: float
    reason: str

    def as_dict(self):
        return asdict(self)


class MarketHealthEngine:
    def __init__(
        self,
        min_samples: int = 5,
        min_win_rate: float = 0.40,
        healthy_win_rate: float = 0.55,
    ):
        self.min_samples = int(min_samples)
        self.min_win_rate = float(min_win_rate)
        self.healthy_win_rate = float(healthy_win_rate)

    def evaluate(self, shadow_observations, paper_trades):
        evidence = {}

        for row in shadow_observations:
            item = dict(row)
            if not item.get("resolved_at"):
                continue
            symbol = str(item["symbol"])
            bucket = evidence.setdefault(symbol, self._bucket())
            net_return = float(item.get("net_return") or 0.0)
            bucket["outcomes"].append(net_return)
            bucket["shadow_returns"].append(net_return)

        for row in paper_trades:
            item = dict(row)
            symbol = str(item["symbol"])
            bucket = evidence.setdefault(symbol, self._bucket())
            pnl = float(item.get("pnl") or 0.0)
            bucket["outcomes"].append(pnl)
            bucket["paper_pnl"] += pnl

        return {
            symbol: self._profile(symbol, values)
            for symbol, values in sorted(evidence.items())
        }

    @staticmethod
    def _bucket():
        return {"outcomes": [], "shadow_returns": [], "paper_pnl": 0.0}

    def _profile(self, symbol, values):
        outcomes = values["outcomes"]
        samples = len(outcomes)
        wins = sum(1 for value in outcomes if value > 0)
        win_rate = wins / samples if samples else 0.0
        shadow_returns = values["shadow_returns"]
        average_shadow_return = (
            sum(shadow_returns) / len(shadow_returns)
            if shadow_returns
            else 0.0
        )

        if samples < self.min_samples:
            status = LEARNING
            reason = f"Needs {self.min_samples - samples} more resolved outcomes."
        elif win_rate < self.min_win_rate or (
            shadow_returns and average_shadow_return < 0
        ):
            status = QUARANTINED
            reason = "Rolling outcomes are below the minimum quality threshold."
        elif win_rate >= self.healthy_win_rate and (
            not shadow_returns or average_shadow_return >= 0
        ):
            status = HEALTHY
            reason = "Rolling outcomes meet the healthy-market threshold."
        else:
            status = LEARNING
            reason = "Evidence is mixed; continue paper and shadow validation."

        return MarketHealthProfile(
            symbol=symbol,
            status=status,
            samples=samples,
            wins=wins,
            win_rate=win_rate,
            average_shadow_return=average_shadow_return,
            paper_pnl=float(values["paper_pnl"]),
            reason=reason,
        )
