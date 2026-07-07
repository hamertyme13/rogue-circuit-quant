from pathlib import Path

import pandas as pd
from rich.console import Console

from backtesting.engine import BacktestEngine
from risk.portfolio import Portfolio
from strategies.momentum import MomentumStrategy

console = Console()

DATA = Path("data/historical/BTC_USD/5m.csv")


def main():

    console.rule("[cyan]Backtest Demo[/cyan]")

    df = pd.read_csv(DATA)

    strategy = MomentumStrategy()

    portfolio = Portfolio()

    engine = BacktestEngine(
        strategy,
        portfolio,
    )

    portfolio = engine.run(df)

    console.print()

    console.print(
        f"Trades Executed : {portfolio.total_trades()}"
    )

    console.print(
        f"Portfolio Equity : ${portfolio.equity():,.2f}"
    )


if __name__ == "__main__":
    main()