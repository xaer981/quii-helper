from unittest.mock import Mock, sentinel

import pytest

from examples import watch_call_events as example
from quii_helper import (
    Camera,
    CameraCallEvent,
    CameraCallEventPage,
    ConfigurationError,
    QuiiConnectionError,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        assert seconds > 0
        self.sleeps.append(seconds)
        self.now += seconds


def history(*record_ids: str) -> CameraCallEventPage:
    return CameraCallEventPage(
        events=[
            CameraCallEvent(
                record_id=record_id,
                alarm_id=f"alarm-{record_id}",
                device_id="test-device",
                channel=0,
                time="2026-11-09 10:00:00",
                alarm_state=0,
                message_state=1,
                message_save_type=0,
                record_url="https://media.example/private-token",
            )
            for record_id in record_ids
        ],
        max_id="pagination-anchor-not-a-polling-cursor",
        total_count=len(record_ids),
        unread_count=0,
    )


@pytest.fixture
def watcher(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, FakeClock]:
    camera = Mock(spec=Camera)
    clock = FakeClock()
    monkeypatch.setattr(example, "Camera", Mock(return_value=camera))
    monkeypatch.setattr(
        example, "load_config", Mock(return_value=sentinel.config)
    )
    monkeypatch.setattr(example, "configure_logging", Mock())
    monkeypatch.setattr(example, "monotonic", clock.monotonic)
    monkeypatch.setattr(example, "sleep", clock.sleep)
    monkeypatch.setattr(example, "WATCH_SECONDS", 20.0)
    return camera, clock


def test_polling_only_reads_fresh_first_pages_and_deduplicates(
    watcher: tuple[Mock, FakeClock], capsys: pytest.CaptureFixture[str]
) -> None:
    camera, clock = watcher
    camera.get_cloud_call_events.side_effect = [
        history("baseline-only"),
        history("first", "first", "baseline-only"),
        history("baseline-only"),
        history("second", "first"),
    ]

    example.main()

    example.Camera.assert_called_once_with(
        config=sentinel.config, connection_mode="cloud"
    )
    example.load_config.assert_called_once_with()
    example.configure_logging.assert_called_once_with(replace_existing=True)
    assert camera.get_cloud_call_events.call_count == 4
    for call in camera.get_cloud_call_events.call_args_list:
        assert call.args == ()
        assert call.kwargs == {"page": 0, "max_id": "0", "page_size": 15}
    assert {call[0] for call in camera.mock_calls} == {"get_cloud_call_events"}
    assert clock.sleeps == [5.0] * 4
    assert clock.now == 20.0
    output = capsys.readouterr().out
    assert "Baseline ready: 1" in output
    assert output.count("record_id=first") == 1
    assert output.count("record_id=second") == 1
    assert "baseline-only" not in output
    assert "private-token" not in output
    assert output.endswith("Stopped.\n")


def test_query_errors_neither_initialize_nor_reset_the_baseline(
    watcher: tuple[Mock, FakeClock], capsys: pytest.CaptureFixture[str]
) -> None:
    camera, _ = watcher
    camera.get_cloud_call_events.side_effect = [
        QuiiConnectionError("private-error-detail"),
        history("baseline-only"),
        QuiiConnectionError("private-error-detail"),
        history("fresh-record", "baseline-only"),
    ]

    example.main()

    output = capsys.readouterr().out
    assert output.count("Cloud history query failed") == 2
    assert output.count("Baseline ready:") == 1
    assert "baseline-only" not in output
    assert output.count("record_id=fresh-record") == 1
    assert "private-error-detail" not in output


def test_empty_successful_page_is_a_valid_baseline(
    watcher: tuple[Mock, FakeClock], capsys: pytest.CaptureFixture[str]
) -> None:
    camera, _ = watcher
    camera.get_cloud_call_events.side_effect = [
        history(),
        history("first-record"),
        history("first-record"),
        history(),
    ]

    example.main()

    output = capsys.readouterr().out
    assert "Baseline ready: 0" in output
    assert output.count("Baseline ready:") == 1
    assert output.count("record_id=first-record") == 1


@pytest.mark.parametrize("query_seconds", [1.25, 25.0])
def test_query_time_counts_towards_poll_interval_and_deadline(
    watcher: tuple[Mock, FakeClock], query_seconds: float
) -> None:
    camera, clock = watcher
    starts = []

    def query(**kwargs: object) -> CameraCallEventPage:
        starts.append(clock.now)
        clock.now += query_seconds
        return history()

    camera.get_cloud_call_events.side_effect = query

    example.main()

    if query_seconds < 5.0:
        assert starts == [0.0, 5.0, 10.0, 15.0]
        assert clock.sleeps == [3.75] * 4
        assert clock.now == 20.0
    else:
        assert starts == [0.0]
        assert clock.sleeps == []


@pytest.mark.parametrize("phase", ["query", "sleep"])
def test_ctrl_c_stops_without_another_query(
    watcher: tuple[Mock, FakeClock],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    phase: str,
) -> None:
    camera, _ = watcher
    if phase == "query":
        camera.get_cloud_call_events.side_effect = KeyboardInterrupt
    else:
        camera.get_cloud_call_events.return_value = history()
        monkeypatch.setattr(
            example, "sleep", Mock(side_effect=KeyboardInterrupt)
        )

    example.main()

    camera.get_cloud_call_events.assert_called_once_with(
        page=0, max_id="0", page_size=15
    )
    assert capsys.readouterr().out.endswith("Stopped.\n")


def test_configuration_errors_are_not_retried(
    watcher: tuple[Mock, FakeClock],
) -> None:
    camera, clock = watcher
    camera.get_cloud_call_events.side_effect = ConfigurationError(
        "missing setting"
    )

    with pytest.raises(ConfigurationError, match="missing setting"):
        example.main()

    assert camera.get_cloud_call_events.call_count == 1
    assert clock.sleeps == []
