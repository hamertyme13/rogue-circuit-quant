from backtesting.metrics import PerformanceMetrics


class BacktestReport:

    def __init__(
        self,
        portfolio,
    ):

        self.portfolio = portfolio

    def print(self):

        metrics = PerformanceMetrics(self.portfolio)

        closed = self.portfolio.closed_trades

        wins = len(
            [
                trade
                for trade in closed
                if trade.pnl > 0
            ]
        )

        losses = len(closed) - wins

        print()

        print("=" * 50)
        print("ROGUE CIRCUIT QUANT REPORT")
        print("=" * 50)

        print(f"Starting Balance : ${self.portfolio.starting_balance:,.2f}")

        print(f"Cash             : ${self.portfolio.cash:,.2f}")

        print(f"Equity           : ${self.portfolio.equity():,.2f}")

        print()

        print(f"Open Trades      : {self.portfolio.open_positions()}")

        print(f"Closed Trades    : {len(closed)}")

        print(f"Total Trades     : {self.portfolio.total_trades()}")

        print()

        print(f"Wins             : {wins}")

        print(f"Losses           : {losses}")

        print()

        print(
            f"Realized PnL     : ${self.portfolio.realized_pnl():,.2f}"
        )

        print()

        print("=" * 50)

        print("RISK")

        print("=" * 50)

        print(
            f"Maximum Drawdown : "
            f"{metrics.max_drawdown()*100:.2f}%"
        )

        print(
            f"Ending Equity : "
            f"${metrics.ending_equity():,.2f}"
        )