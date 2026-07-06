from rich.console import Console
from rich.progress import track
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

    for symbol in track(SYMBOLS, description="Downloading Market Data..."):

        service.download_symbol(
            symbol,
            TIMEFRAMES[0],      
        )

    console.print()

    console.print(
        "Historical download complete.",
        style="bold green",
    )


if __name__ == "__main__":
    main()