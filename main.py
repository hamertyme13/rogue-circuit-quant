from pathlib import Path

import pandas as pd
from rich.console import Console
from indicators.engine import IndicatorEngine
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

    engine = IndicatorEngine([
        SMA(20),
        EMA(20),
        RSI(14),
    ])

    df = engine.calculate(df)

    console.print(df.tail())

    console.print()

    console.print(
        "[green]Indicator calculations successful![/green]"
    )


if __name__ == "__main__":
    main()