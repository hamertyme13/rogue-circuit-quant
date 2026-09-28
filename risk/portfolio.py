from models.trade import Trade
from risk.fees import FeeModel

fee_model = FeeModel()


class Portfolio:

    def __init__(self, starting_balance: float = 10_000):

        self.starting_balance = starting_balance

        self.cash = starting_balance

        self.open_trades = []

        self.closed_trades = []

        self.equity_history = []

        self.high_water_mark = starting_balance

        self.market_prices = {}

    # -----------------------------
    # Position Management
    # -----------------------------

    def open_trade(self, trade: Trade):

        if trade.entry_notional == 0:
            trade.entry_notional = trade.entry_price * trade.quantity

        if trade.entry_fee == 0:
            trade.entry_fee = fee_model.calculate(trade.entry_notional)

        self.cash -= trade.entry_notional + trade.entry_fee
        self.open_trades.append(trade)
        self.update_market_price(
            trade.symbol,
            trade.entry_price,
        )
        self.record_equity()

    def close_trade(
        self,
        trade: Trade,
        exit_price: float,
        exit_time,
    ):

        trade.exit_price = exit_price

        trade.exit_time = exit_time

        gross = (
            exit_price
            - trade.entry_price
        ) * trade.quantity

        proceeds = exit_price * trade.quantity

        fees = fee_model.calculate(proceeds)

        trade.exit_fee = fees

        trade.pnl = gross - trade.entry_fee - fees

        trade.status = "CLOSED"

        self.cash += proceeds - fees

        self.open_trades.remove(trade)

        self.closed_trades.append(trade)

        self.record_equity()

    # -----------------------------
    # Statistics
    # -----------------------------

    def total_trades(self):

        return len(self.open_trades) + len(self.closed_trades)

    def open_positions(self):

        return len(self.open_trades)

    def has_open_position(self):

        return len(self.open_trades) > 0

    def open_position_for(self, symbol: str):

        for trade in self.open_trades:
            if trade.symbol == symbol:
                return trade

        return None

    def has_open_position_for(self, symbol: str):

        return self.open_position_for(symbol) is not None

    def realized_pnl(self):

        return sum(
            trade.pnl
            for trade in self.closed_trades
        )

    def equity(self):

        return self.account_value()

    def position_value(self):

        total = 0.0

        for trade in self.open_trades:
            price = self.market_prices.get(
                trade.symbol,
                trade.entry_price,
            )
            total += price * trade.quantity

        return total

    def update_market_price(
        self,
        symbol: str,
        price: float,
    ):

        if symbol:
            self.market_prices[symbol] = float(price)
    
    def account_value(self):

        return self.cash + self.position_value()


    def drawdown_percent(self):

        if self.high_water_mark == 0:

            return 0
        
        return max(
            0,
            (
                self.high_water_mark
                - self.account_value()
            ) / self.high_water_mark
        )


    def daily_loss_percent(self):

        loss = self.starting_balance - self.account_value()

        return max(
            0,
            loss / self.starting_balance,
        )
    
    def record_equity(self):

        equity = self.account_value()

        self.equity_history.append(equity)

        if equity > self.high_water_mark:

            self.high_water_mark = equity
