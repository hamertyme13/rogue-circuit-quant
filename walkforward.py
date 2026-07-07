from pathlib import Path

import pandas as pd
from rich.console import Console

from optimization.walk_forward import WalkForwardTest
from reporting.tables import ReportTables
from analytics.verdict import VerdictEngine

console = Console()

DATA = Path("data/historical/BTC_USD/5m.csv")


def main():

    console.rule("[cyan]Walk-Forward Validation[/cyan]")

    df = pd.read_csv(DATA)

    best, metrics = WalkForwardTest().run(df)

    console.print()

    console.print("[bold green]Best Training Strategy[/bold green]")

    ReportTables.training_result(best)

    ReportTables.validation_result(metrics)

    verdict = VerdictEngine().evaluate(metrics)

    console.print()

    console.rule("[bold yellow]Research Verdict[/bold yellow]")

    if verdict.passed:

        console.print(
            "[bold green]✅ PASSED VALIDATION[/bold green]"
        )

    else:

        console.print(
            "[bold red]❌ FAILED VALIDATION[/bold red]"
        )

    console.print()

    console.print(
        f"Research Score : {verdict.score}/100"
    )

    console.print()

    console.print("Reasons:")

    for reason in verdict.reasons:

        console.print(
            f" • {reason}"
        )


if __name__ == "__main__":
    main()