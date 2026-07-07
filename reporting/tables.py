from rich.console import Console
from rich.table import Table
from reporting.colors import ColorEngine

console = Console()


class ReportTables:

    @staticmethod
    def training_result(best):

        table = Table(
            title="🏆 Best Training Strategy",
            show_lines=True,
        )

        table.add_column(
            "Metric",
            style="cyan",
        )

        table.add_column(
            "Value",
            style="green",
        )

        table.add_row(
            "Fast EMA",
            str(best.fast_ema),
        )

        table.add_row(
            "Slow EMA",
            str(best.slow_ema),
        )

        table.add_row(
            "RSI Period",
            str(best.rsi_period),
        )

        table.add_row(
            "Buy RSI",
            str(best.buy_rsi),
        )

        table.add_row(
            "Sell RSI",
            str(best.sell_rsi),
        )

        table.add_row(
            "Trades",
            str(best.trades),
        )

        table.add_row(
            "Win Rate",
            ColorEngine.win_rate(best.win_rate)
        )

        table.add_row(
            "Net Profit",
            ColorEngine.profit(best.net_profit)
        )

        table.add_row(
            "Drawdown",
            ColorEngine.drawdown(best.drawdown)
        )

        console.print(table)

    @staticmethod
    def validation_result(metrics):

        table = Table(
            title="📈 Validation Results",
            show_lines=True,
        )

        table.add_column(
            "Metric",
            style="cyan",
        )

        table.add_column(
            "Value",
            style="magenta",
        )

        table.add_row(
            "Win Rate",
            ColorEngine.win_rate(
                metrics.win_rate()
            )
        )

        table.add_row(
            "Net Profit",
            ColorEngine.profit(
                metrics.total_profit()
            )
        )

        table.add_row(
            "Drawdown",
            ColorEngine.drawdown(
                metrics.max_drawdown()
            )
        )

        console.print(table)