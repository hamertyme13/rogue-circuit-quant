from pathlib import Path

import pandas as pd
from rich.console import Console
from backtesting.equity_curve import EquityCurve
from backtesting.engine import BacktestEngine
from backtesting.report import BacktestReport
from backtesting.metrics import PerformanceMetrics
from risk.portfolio import Portfolio
from strategies.momentum import MomentumStrategy
from config import PAPER_TRADING

console = Console()

DATA = Path(
    "data/historical/BTC_USD/5m.csv"
)


def main():

    if PAPER_TRADING:

        console.print(
            "[bold yellow]MODE PAPER TRADING[/bold yellow]"
        )
    else:

        console.print(
            "[bold red]MODE: LIVE TRADING[/bold red]"
        )

    console.rule("[cyan]Backtesting Engine[/cyan]")

    df = pd.read_csv(DATA)

    portfolio = Portfolio()

    engine = BacktestEngine(
        MomentumStrategy(
            fast_ema=10,
            slow_ema=40,
            rsi_period=10,
            buy_rsi=60,
            sell_rsi=40,
        ),
        portfolio,
    )

    portfolio = engine.run(df)

    console.print()

    console.print(
        f"Trades : {portfolio.total_trades()}"
    )

    console.print(
        f"Open Positions : {portfolio.open_positions()}"
    )

    console.print(
        f"Equity : ${portfolio.equity():,.2f}"
    )

    report = BacktestReport(portfolio)

    report.print()

    EquityCurve(portfolio).show()

    metrics = PerformanceMetrics(portfolio)

    print()

    print("=" * 50)

    print("PERFORMANCE")

    print("=" * 50)

    print(
        f"Win Rate : {metrics.win_rate()*100:.2f}%"
    )

    print(
        f"Net Profit : ${metrics.total_profit():,.2f}"
    )


if __name__ == "__main__":
    main()

