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

    # -----------------------------
    # Position Management
    # -----------------------------

    def open_trade(self, trade: Trade):

        self.open_trades.append(trade)

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

        fees = fee_model.calculate(
            exit_price * trade.quantity
        )

        trade.pnl = gross - fees

        trade.status = "CLOSED"

        self.cash += trade.pnl

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

    def realized_pnl(self):

        return sum(
            trade.pnl
            for trade in self.closed_trades
        )

    def equity(self):

        return self.cash
    
    def account_value(self):

        return self.cash


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

        loss = self.starting_balance - self.cash

        return max(
            0,
            loss / self.starting_balance,
        )
    
    def record_equity(self):

        equity = self.account_value()

        self.equity_history.append(equity)

        if equity > self.high_water_mark:

            self.high_water_mark = equity