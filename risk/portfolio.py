from models.trade import Trade


class Portfolio:

    def __init__(
        self,
        starting_balance: float = 10000,
    ):
        self.cash = starting_balance
        self.trades: list[Trade] = []

    def add_trade(
        self,
        trade: Trade,
    ):
        self.trades.append(trade)

    def total_trades(self):

        return len(self.trades)

    def equity(self):

        pnl = sum(
            trade.pnl
            for trade in self.trades
        )

        return self.cash + pnl