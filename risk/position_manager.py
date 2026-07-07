from models.trade import Trade


class PositionManager:

    def __init__(self, portfolio):
        self.portfolio = portfolio

    def open_position(self, signal, quantity):

        trade = Trade(
            strategy=signal.strategy,
            entry_time=signal.timestamp,
            entry_price=signal.price,
            quantity=quantity,
        )

        self.portfolio.open_trade(trade)

    def close_position(self, signal):

        if not self.portfolio.open_trades:
            return

        trade = self.portfolio.open_trades[0]

        self.portfolio.close_trade(
            trade,
            signal.price,
            signal.timestamp,
        )