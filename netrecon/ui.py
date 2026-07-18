"""Rich/pyfiglet TUI helpers: banner, menus, tables, prompts. No curses, no mouse."""
from __future__ import annotations

from dataclasses import is_dataclass, asdict
from typing import Any, Optional

import pyfiglet
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.text import Text

from . import config

console = Console()


def theme_color() -> str:
    return config.get_config().get("color_theme", "cyan")


def print_banner() -> None:
    cfg = config.get_config()
    text = cfg.get("banner_text", "NETRECON")
    font = cfg.get("banner_font", "slant")
    try:
        art = pyfiglet.figlet_format(text, font=font)
    except pyfiglet.FontNotFound:
        art = pyfiglet.figlet_format(text)
    color = theme_color()
    console.print(f"[{color}]{art}[/{color}]", highlight=False)
    console.print(Panel.fit(
        "network + bluetooth recon — discovery & enumeration only, no attacks",
        style=f"{color}",
    ))


def print_error(msg: str) -> None:
    console.print(f"[bold red]✗[/bold red] {msg}")


def print_warning(msg: str) -> None:
    console.print(f"[bold yellow]![/bold yellow] {msg}")


def print_success(msg: str) -> None:
    console.print(f"[bold green]✓[/bold green] {msg}")


def print_info(msg: str) -> None:
    console.print(f"[bold {theme_color()}]i[/bold {theme_color()}] {msg}")


class MenuItem:
    def __init__(self, label: str, action, enabled: bool = True, disabled_reason: str = ""):
        self.label = label
        self.action = action
        self.enabled = enabled
        self.disabled_reason = disabled_reason


def show_menu(title: str, items: list[MenuItem], allow_back: bool = True) -> bool:
    """Numbered menu loop. Returns True if the user explicitly chose 0 (back/exit),
    False if the prompt was interrupted (Ctrl-C/EOF) instead."""
    color = theme_color()
    while True:
        table = Table(title=title, title_style=f"bold {color}", show_header=False, box=None)
        table.add_column("n", style=color, width=4)
        table.add_column("label")

        for idx, item in enumerate(items, start=1):
            if item.enabled:
                table.add_row(str(idx), item.label)
            else:
                reason = f" [dim]({item.disabled_reason})[/dim]" if item.disabled_reason else ""
                table.add_row(str(idx), f"[dim strike]{item.label}[/dim strike]{reason}")

        back_label = "Back" if allow_back else "Exit"
        table.add_row("0", back_label)
        console.print(table)

        try:
            choice = Prompt.ask("Select", default="0")
        except (KeyboardInterrupt, EOFError):
            console.print()
            return False

        choice = choice.strip()
        if choice == "0":
            return True
        if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
            print_error("Invalid selection")
            continue

        item = items[int(choice) - 1]
        if not item.enabled:
            print_warning(f"Unavailable: {item.disabled_reason}")
            continue

        try:
            item.action()
        except KeyboardInterrupt:
            console.print()
            print_warning("Interrupted — back to menu")
        except Exception as exc:  # the TUI must never die from a module error
            print_error(f"Unexpected error: {exc}")


def ask(prompt: str, default: Optional[str] = None) -> str:
    try:
        return Prompt.ask(prompt, default=default) if default is not None else Prompt.ask(prompt)
    except (KeyboardInterrupt, EOFError):
        raise KeyboardInterrupt


def confirm(prompt: str, default: bool = False) -> bool:
    try:
        return Confirm.ask(prompt, default=default)
    except (KeyboardInterrupt, EOFError):
        raise KeyboardInterrupt


def _plain(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _plain(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_plain(v) for v in obj]
    return obj


def render_table(title: str, rows: list, columns: Optional[list[str]] = None) -> None:
    """Render a list of dataclasses/dicts as a rich table."""
    color = theme_color()
    if not rows:
        console.print(Panel(f"No results.", title=title, style="dim"))
        return

    plain_rows = [_plain(r) for r in rows]
    cols = columns or list(plain_rows[0].keys())

    table = Table(title=title, title_style=f"bold {color}", header_style=f"bold {color}")
    for c in cols:
        table.add_column(c)
    for row in plain_rows:
        table.add_row(*[str(row.get(c, "")) for c in cols])
    console.print(table)


def render_kv_panel(title: str, data: dict) -> None:
    color = theme_color()
    body = "\n".join(f"[bold]{k}[/bold]: {v}" for k, v in data.items())
    console.print(Panel(body or "(empty)", title=title, border_style=color))
