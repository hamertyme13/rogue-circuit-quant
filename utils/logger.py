from rich.console import Console

console = Console()


def info(message: str):
    console.print(f"[cyan][INFO][/cyan] {message}")


def success(message: str):
    console.print(f"[green][SUCCESS][/green] {message}")


def warning(message: str):
    console.print(f"[yellow][WARNING][/yellow] {message}")


def error(message: str):
    console.print(f"[red][ERROR][/red] {message}")