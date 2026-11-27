"""Optional styling for interactive terminals; keep redirected output plain."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from rich.console import Console


def display_path(path: Path) -> str:
    """Keep Unicode paths copyable without emitting terminal controls."""
    return "".join(
        char if char.isprintable() else ascii(char)[1:-1]
        for char in path.as_posix()
    )


def rich_console(stream: TextIO) -> Console | None:
    if not stream.isatty():
        return None
    try:
        from rich.console import Console
    except ImportError:
        return None
    return Console(
        file=stream,
        color_system=None if "NO_COLOR" in os.environ else "auto",
        markup=False,
        highlight=False,
    )


def print_status(text: str, style: str, *, file: TextIO | None = None) -> None:
    stream = sys.stdout if file is None else file
    console = rich_console(stream)
    if console is None:
        print(text, file=stream, flush=True)
    else:
        console.print(text, style=style, soft_wrap=True)
        stream.flush()


def rich_table(
    headers: Sequence[str], rows: Iterable[Sequence[str]], *, file: TextIO
) -> bool:
    console = rich_console(file)
    if console is None:
        return False
    from rich.table import Table
    from rich.text import Text

    table = Table(box=None, header_style="bold cyan", pad_edge=False)
    for index, label in enumerate(headers):
        table.add_column(label, style="bold cyan" if index == 0 else None)
    for row in rows:
        table.add_row(*(Text(cell, overflow="ellipsis") for cell in row))
    console.print(table)
    return True
