"""Check opt-in styling without requiring a physical terminal."""

import sys
from io import StringIO
from pathlib import Path

import pytest

from quii_helper.cli.presentation import display_path, print_status, rich_table


class Terminal(StringIO):
    def isatty(self):
        return True


def test_display_path_escapes_control_characters_but_keeps_unicode():
    assert (
        display_path(Path("\u0444\u0430\u0439\u043b\n\x1b.jpg"))
        == "\u0444\u0430\u0439\u043b\\n\\x1b.jpg"
    )


def test_no_styling_when_redirected_or_rich_is_missing(monkeypatch):
    stream = StringIO()
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert not rich_table(["#"], [["1"]], file=stream)
    print_status("Ready", "green", file=stream)
    assert stream.getvalue() == "Ready\n"

    monkeypatch.setitem(sys.modules, "rich.console", None)
    terminal = Terminal()
    assert not rich_table(["#"], [["1"]], file=terminal)
    print_status("Ready", "green", file=terminal)
    assert terminal.getvalue() == "Ready\n"


def test_rich_renders_text_literally_and_respects_no_color(monkeypatch):
    pytest.importorskip("rich")
    monkeypatch.setenv("NO_COLOR", "1")
    terminal = Terminal()
    assert rich_table(["#", "TYPE"], [["1", "[red]video"]], file=terminal)
    print_status("Ready: [private]", "green", file=terminal)
    output = terminal.getvalue()
    assert "[red]video" in output and "Ready: [private]" in output
    assert "\x1b" not in output
