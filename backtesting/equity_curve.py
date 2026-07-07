import matplotlib.pyplot as plt


class EquityCurve:

    def __init__(self, portfolio):

        self.portfolio = portfolio

    def show(self):

        plt.figure(figsize=(12,6))

        plt.plot(

            self.portfolio.equity_history,

            linewidth=2,

        )

        plt.title("Portfolio Equity Curve")

        plt.xlabel("Closed Trades")

        plt.ylabel("Account Value ($)")

        plt.grid(True)

        plt.tight_layout()

        plt.show()