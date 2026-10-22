import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import quii_helper
from quii_helper.support import log


def test_configure_logging_removes_only_its_own_sink(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = MagicMock()
    logger.add.side_effect = [51, 52]
    monkeypatch.setattr(log, "logger", logger)
    monkeypatch.setattr(log, "_SINK_ID", None)
    log.configure_logging("INFO")
    logger.remove.assert_not_called()
    log.configure_logging("DEBUG")
    logger.remove.assert_called_once_with(51)


def test_explicit_standalone_configuration_can_replace_all_sinks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = MagicMock()
    monkeypatch.setattr(log, "logger", logger)
    monkeypatch.setattr(log, "_SINK_ID", None)
    log.configure_logging("INFO", replace_existing=True)
    logger.remove.assert_called_once_with()


def test_console_level_and_reconfiguration_preserve_host_logging(
    tmp_path: Path,
) -> None:
    code = """
import contextlib
import io
from loguru import logger
from quii_helper.support.log import configure_logging
logger.remove()
host = []
sink = logger.add(lambda message: host.append(str(message)))
output = io.StringIO()
with contextlib.redirect_stderr(output):
    configure_logging('INFO')
    configure_logging('INFO')
    namespace = {'__name__': 'quii_helper.tests', 'logger': logger}
    exec('def emit(level, message): logger.log(level, message)', namespace)
    emit = namespace['emit']
    emit('DEBUG', 'debug-only')
    emit('INFO', 'one-console-message')
    configure_logging('OFF')
    emit('INFO', 'library-disabled')
logger.info('host-still-works')
logger.remove(sink)
assert output.getvalue().count('one-console-message') == 1
assert 'debug-only' not in output.getvalue()
assert 'library-disabled' not in ''.join(host)
assert 'host-still-works' in ''.join(host)
"""
    root = str(Path(quii_helper.__file__).parents[1])
    code = f"import sys; sys.path.insert(0, {root!r})\n" + code
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
