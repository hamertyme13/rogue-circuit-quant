from dataclasses import asdict
from datetime import datetime, timezone

from models.trade import Trade
from risk.portfolio import Portfolio


class PaperRuntimeState:
    VERSION = 2

    def export(self, trader, evidence):
        portfolio = trader.portfolio
        return {
            "version": self.VERSION,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "cycles": int(trader.cycles),
            "evidence": {
                key: int(evidence.get(key, 0))
                for key in self.empty_evidence()
            },
            "portfolio": {
                "starting_balance": float(portfolio.starting_balance),
                "cash": float(portfolio.cash),
                "high_water_mark": float(portfolio.high_water_mark),
                "market_prices": dict(portfolio.market_prices),
                "equity_history": [float(value) for value in portfolio.equity_history[-500:]],
                "open_trades": [self._trade_payload(trade) for trade in portfolio.open_trades],
                "closed_trades": [self._trade_payload(trade) for trade in portfolio.closed_trades],
            },
        }

    def restore(self, trader, payload):
        version = int(payload.get("version", 0)) if payload else 0
        if version not in {1, self.VERSION}:
            return self.empty_evidence(), False

        data = payload.get("portfolio") or {}
        portfolio = Portfolio(float(data.get("starting_balance", 10_000)))
        portfolio.cash = float(data.get("cash", portfolio.starting_balance))
        portfolio.high_water_mark = float(
            data.get("high_water_mark", portfolio.starting_balance)
        )
        portfolio.market_prices = {
            str(symbol): float(price)
            for symbol, price in (data.get("market_prices") or {}).items()
        }
        portfolio.equity_history = [
            float(value) for value in data.get("equity_history", [])
        ]
        portfolio.open_trades = [
            self._restore_trade(item) for item in data.get("open_trades", [])
        ]
        portfolio.closed_trades = [
            self._restore_trade(item) for item in data.get("closed_trades", [])
        ]
        for trade in portfolio.closed_trades:
            trade._web_ledger_recorded = True

        trader.portfolio = portfolio
        trader.risk.portfolio = portfolio
        trader.positions.portfolio = portfolio
        trader.cycles = int(payload.get("cycles", 0))
        evidence = self.empty_evidence()
        if version == 1:
            evidence["legacy_cycles"] = int(
                (payload.get("evidence") or {}).get("cycles", 0)
            )
        else:
            evidence.update(payload.get("evidence") or {})
        return {key: int(value) for key, value in evidence.items()}, True

    @staticmethod
    def empty_evidence():
        return {
            "cycles": 0,
            "total_events": 0,
            "executed_events": 0,
            "opportunity_events": 0,
            "unverified_cycles": 0,
            "legacy_cycles": 0,
        }

    @staticmethod
    def _trade_payload(trade):
        payload = asdict(trade)
        payload["entry_time"] = trade.entry_time.isoformat()
        payload["exit_time"] = (
            trade.exit_time.isoformat() if trade.exit_time else None
        )
        return payload

    @staticmethod
    def _restore_trade(payload):
        data = dict(payload)
        data["entry_time"] = datetime.fromisoformat(data["entry_time"])
        if data.get("exit_time"):
            data["exit_time"] = datetime.fromisoformat(data["exit_time"])
        return Trade(**data)
