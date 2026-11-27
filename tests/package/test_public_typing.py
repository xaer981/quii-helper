"""Check the same RTSP types that a library consumer's editor sees."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

IMPORTS = """
from quii_helper.camera.streaming import CameraRtspStream
from quii_helper.config import AutonomousConfig
"""


@pytest.mark.parametrize(
    "source,errors",
    [
        (
            """
def inspect_session(session: CameraRtspStream) -> tuple[int, bool, AutonomousConfig]:
    frames: int = session.stats['h264']['frames']
    buffered: int = session.stats['h264']['cframe_pack']['trailing_partial_bytes']
    active: bool = session.stats['talk_active']
    config: AutonomousConfig = session.connector.config
    return frames + buffered, active, config
""",
            [],
        ),
        (
            """
def invalid_session(session: CameraRtspStream) -> None:
    session.stats['rtsp_clients'] = 'not an integer'
    session.stats['h264']['missing_counter']
    session.connector.not_a_connector_method()
""",
            [
                "[typeddict-item]",
                "[attr-defined]",
                "rtsp_clients",
                "missing_counter",
                "not_a_connector_method",
            ],
        ),
    ],
)
def test_consumer_rtsp_types_are_checked(source, errors, tmp_path):
    pytest.importorskip("mypy")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            os.devnull,
            "--python-version",
            "3.10",
            "--follow-imports=silent",
            "--ignore-missing-imports",
            "--strict",
            "--no-incremental",
            "--cache-dir",
            str(tmp_path / "mypy"),
            "-c",
            IMPORTS + source,
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == (1 if errors else 0), (
        result.stdout + result.stderr
    )
    for error in errors:
        assert error in result.stdout
