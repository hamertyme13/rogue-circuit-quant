class ColorEngine:

    @staticmethod
    def profit(value: float):

        if value > 0:
            return f"[green]+${value:.2f}[/green]"

        if value < 0:
            return f"[red]-${abs(value):.2f}[/red]"

        return "$0.00"

    @staticmethod
    def percentage(value: float):

        return f"{value*100:.2f}%"

    @staticmethod
    def drawdown(value: float):

        percent = value * 100

        if percent < 5:
            return f"[green]{percent:.2f}%[/green]"

        if percent < 10:
            return f"[yellow]{percent:.2f}%[/yellow]"

        return f"[red]{percent:.2f}%[/red]"

    @staticmethod
    def win_rate(value: float):

        percent = value * 100

        if percent >= 60:
            return f"[green]{percent:.2f}%[/green]"

        if percent >= 50:
            return f"[yellow]{percent:.2f}%[/yellow]"

        return f"[red]{percent:.2f}%[/red]"