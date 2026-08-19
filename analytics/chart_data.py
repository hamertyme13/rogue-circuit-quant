from __future__ import annotations


class ChartDataBuilder:

    def build(self, ledger):

        snapshots = ledger.snapshots()
        summary = ledger.summary()

        equity_curve = [
            {
                "timestamp": snapshot.timestamp,
                "value": snapshot.total_value,
                "source": snapshot.source,
            }
            for snapshot in snapshots
        ]
        drawdown = self._drawdown(equity_curve)
        daily_pnl = self._daily_pnl(equity_curve)

        return {
            "equity_curve": equity_curve,
            "drawdown": drawdown,
            "daily_pnl": daily_pnl,
            "deposits": summary.deposits,
            "withdrawals": summary.withdrawals,
            "net_deposits": summary.net_deposits,
            "net_growth": summary.net_growth,
        }

    def _drawdown(self, equity_curve):

        high_water = 0.0
        result = []

        for point in equity_curve:
            value = point["value"]
            high_water = max(high_water, value)
            drawdown = (
                0.0
                if high_water == 0
                else (high_water - value) / high_water
            )
            result.append({
                "timestamp": point["timestamp"],
                "drawdown": drawdown,
            })

        return result

    def _daily_pnl(self, equity_curve):

        result = []
        previous = None

        for point in equity_curve:
            value = point["value"]
            pnl = 0.0 if previous is None else value - previous
            previous = value
            result.append({
                "timestamp": point["timestamp"],
                "pnl": pnl,
            })

        return result
