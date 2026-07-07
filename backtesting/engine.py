from models.trade import Trade
from risk.portfolio import Portfolio


class BacktestEngine:

    def __init__(
        self,
        strategy,
        portfolio: Portfolio,
    ):
        self.strategy = strategy
        self.portfolio = portfolio

    def run(self, df):

        signals = self.strategy.generate_signals(df)

        for signal in signals:

            trade = Trade(
                strategy=signal.strategy,
                entry_time=signal.timestamp,
                entry_price=signal.price,
                quantity=1,
            )

            self.portfolio.add_trade(trade)

        return self.portfolio