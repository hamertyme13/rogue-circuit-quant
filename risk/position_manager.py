from models.trade import Trade


class PositionManager:

    def __init__(self, portfolio):
        self.portfolio = portfolio

    def open_position(
        self,
        symbol,
        signal,
        quantity,
        order_id="",
        order_status="",
        fill_price=None,
    ):

        entry_price = float(fill_price or signal.price)

        trade = Trade(
            strategy=signal.strategy,
            entry_time=signal.timestamp,
            symbol=symbol,
            entry_price=entry_price,
            quantity=quantity,
            entry_notional=entry_price * quantity,
            order_id=order_id,
            order_status=order_status,
        )

        self.portfolio.open_trade(trade)

        return trade

    def close_position(self, symbol, signal):

        trade = self.portfolio.open_position_for(symbol)

        if trade is None:
            return

        self.portfolio.close_trade(
            trade,
            signal.price,
            signal.timestamp,
        )

        return trade
