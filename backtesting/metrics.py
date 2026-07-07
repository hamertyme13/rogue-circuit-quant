class PerformanceMetrics:

    def __init__(self, portfolio):

        self.portfolio = portfolio

    def win_rate(self):

        closed = self.portfolio.closed_trades

        if not closed:
            return 0

        wins = len(
            [
                t
                for t in closed
                if t.pnl > 0
            ]
        )

        return wins / len(closed)

    def total_profit(self):

        return sum(
            t.pnl
            for t in self.portfolio.closed_trades
        )
    
    def max_drawdown(self):

        return self.portfolio.drawdown_percent()
    
    def ending_equity(self):

        return self.portfolio.account_value()