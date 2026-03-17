"""Shared Rich console instance."""

from rich.console import Console

console = Console()
err_console = Console(stderr=True)
