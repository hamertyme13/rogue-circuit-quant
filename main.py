from rich.console import Console

from config import (
    PROJECT_NAME,
    VERSION,
    SYMBOLS,
    TIMEFRAMES,
)

from services.historical_data_service import (
    HistoricalDataService,
)

console = Console()


def main():

    console.rule(
        f"[cyan]{PROJECT_NAME} v{VERSION}[/cyan]"
    )

    service = HistoricalDataService()

    for symbol in SYMBOLS:

        service.download_symbol(
            symbol,
            TIMEFRAMES[0],      # 5m for now
        )

    console.print()

    console.print(
        "Historical download complete.",
        style="bold green",
    )


if __name__ == "__main__":
    main()