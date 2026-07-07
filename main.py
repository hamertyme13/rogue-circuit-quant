from pathlib import Path

import pandas as pd
from rich.console import Console

from indicators.ema import EMA
from indicators.rsi import RSI
from indicators.sma import SMA

console = Console()

DATA = Path(
    "data/historical/BTC_USD/5m.csv"
)


def main():

    console.rule("[cyan]Indicator Engine[/cyan]")

    df = pd.read_csv(DATA)

    df = SMA(period=20).calculate(df)

    df = EMA(period=20).calculate(df)

    df = RSI(period=14).calculate(df)

    console.print(df.tail())

    console.print()

    console.print(
        "[green]Indicator calculations successful![/green]"
    )


if __name__ == "__main__":
    main()