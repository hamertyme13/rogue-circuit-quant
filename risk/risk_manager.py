from config import (
    MAX_OPEN_POSITIONS,
    MAX_DAILY_LOSS,
    MAX_DRAWDOWN,
)


class RiskManager:

    def __init__(self, portfolio):

        self.portfolio = portfolio

    def can_open_trade(self):

        if self.portfolio.open_positions() >= MAX_OPEN_POSITIONS:
            return False

        if self.portfolio.daily_loss_percent() >= MAX_DAILY_LOSS:
            return False

        if self.portfolio.drawdown_percent() >= MAX_DRAWDOWN:
            return False

        return True