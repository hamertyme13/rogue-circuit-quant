from rich.console import Console

from exchange.client import KrakenClient

console = Console()


def main():

    console.rule("[cyan]Rogue Circuit Quant[/cyan]")

    client = KrakenClient()

    console.print(
        "Connecting to Kraken...",
        style="yellow",
    )

    markets = client.load_markets()

    console.print(
        f"Connected! {len(markets)} markets loaded.",
        style="green",
    )

    ticker = client.fetch_ticker("BTC/USD")

    console.print()

    console.print(
        "BTC/USD",
        style="bold cyan",
    )

    console.print(
        f"Last Price : ${ticker['last']:,.2f}"
    )

    console.print(
        f"24h High   : ${ticker['high']:,.2f}"
    )

    console.print(
        f"24h Low    : ${ticker['low']:,.2f}"
    )

    console.print(
        f"Volume     : {ticker['baseVolume']:,.2f} BTC"
    )


if __name__ == "__main__":
    main()