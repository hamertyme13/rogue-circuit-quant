from models.trade import Trade
from risk.position_size import PositionSizer
from risk.risk_manager import RiskManager
from risk.position_manager import PositionManager


class ExecutionEngine:

    def __init__(self, portfolio):

        self.portfolio = portfolio

        self.position_sizer = PositionSizer()

        self.risk = RiskManager(portfolio)

        self.position_manager = PositionManager(portfolio)

    def execute(self, signal):

        if signal.action == "BUY":

            if not self.risk.can_open_trade():

                return

            quantity = self.position_sizer.calculate_quantity(
                self.portfolio.cash,
                signal.price,
            )

            self.position_manager.open_position(
                signal,
                quantity,
            )

        elif signal.action == "SELL":

            if not self.portfolio.has_open_position():

                return

            self.position_manager.close_position(signal)