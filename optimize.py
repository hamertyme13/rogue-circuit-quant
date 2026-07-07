from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table

from optimization.optimizer import StrategyOptimizer

console = Console()

DATA = Path("data/historical/BTC_USD/5m.csv")


def main():

    console.rule("[cyan]Strategy Optimizer[/cyan]")

    df = pd.read_csv(DATA)

    optimizer = StrategyOptimizer()

    results = optimizer.optimize(df)

    results.sort(
        key=lambda x: x.net_profit,
        reverse=True,
    )

    table = Table(title="Top Strategy Results")

    table.add_column("Rank")
    table.add_column("Fast EMA")
    table.add_column("Slow EMA")
    table.add_column("RSI")
    table.add_column("Trades")
    table.add_column("Win Rate")
    table.add_column("Profit")
    table.add_column("Drawdown")

    for rank, result in enumerate(results[:10], start=1):

        table.add_row(
            str(rank),
            str(result.fast_ema),
            str(result.slow_ema),
            str(result.rsi_period),
            str(result.trades),
            f"{result.win_rate * 100:.2f}%",
            f"${result.net_profit:.2f}",
            f"{result.drawdown * 100:.2f}%",
        )

    console.print(table)


if __name__ == "__main__":
    main()