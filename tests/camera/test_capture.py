import unittest
from pathlib import Path
from types import SimpleNamespace

from quii_helper.camera.runtime.capture import capture_preview_summary
from quii_helper.preview.pipeline.config import (
    DEFAULT_PREVIEW_CAPTURE_SETTINGS,
)


class _FakeSession:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.tunnel = object()
        self.credentials = SimpleNamespace(data_encode_key="data-key")

    def __enter__(self) -> "_FakeSession":
        self.events.append("session.enter")
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.events.append("session.exit")

    def connection_summary(self) -> dict[str, bool]:
        self.events.append("session.connection_summary")
        return {"connected": True}

    def start_live_preview(
        self, *, setup_seq: int, play_seq: int, setup_timeout: float
    ) -> bool:
        self.events.append(
            f"session.start_live_preview:{setup_seq}:{play_seq}:"
            f"{setup_timeout}"
        )
        return True


class _FakeConnector:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.runtime_credentials = object()
        self.session = _FakeSession(events)

    def fetch_credentials(self) -> object:
        self.events.append("connector.fetch_credentials")
        return self.runtime_credentials

    def open_preview(self, *, credentials: object) -> _FakeSession:
        self.events.append("connector.open_preview")
        if credentials is not self.runtime_credentials:
            raise AssertionError("unexpected credentials")
        return self.session


class _FakePipeline:
    def __init__(self, events: list[str], summary: dict) -> None:
        self.events = events
        self.summary = summary

    def capture(self) -> dict:
        self.events.append("pipeline.capture")
        return self.summary


class _FakePipelineFactory:
    instances: list["_FakePipelineFactory"] = []
    events: list[str] = []
    summary = {
        "media_result": {
            "mp4": True,
            "mp4_path": "video.mp4",
            "written": True,
        }
    }

    def __init__(
        self,
        *,
        preview_settings: object,
        emit: object,
        data_dir: Path,
        render_snapshot: bool,
        render_video: bool,
    ) -> None:
        self.events.append("pipeline_factory.init")
        self.preview_settings = preview_settings
        self.emit = emit
        self.data_dir = data_dir
        self.render_snapshot = render_snapshot
        self.render_video = render_video
        self.create_kwargs = {}
        self.instances.append(self)

    def create(self, **kwargs: object) -> _FakePipeline:
        self.events.append("pipeline_factory.create")
        self.create_kwargs = kwargs
        return _FakePipeline(self.events, self.summary)


class CameraCaptureFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        _FakePipelineFactory.instances = []
        _FakePipelineFactory.events = []

    def test_capture_preview_summary_preserves_orchestration_contract(
        self,
    ) -> None:
        events: list[str] = []
        statuses: list[str] = []
        emitted: list[object] = []
        emit = emitted.append
        connector = _FakeConnector(events)
        data_dir = Path("data")
        output_base = Path("clip")

        summary = capture_preview_summary(
            connector=connector,
            settings=DEFAULT_PREVIEW_CAPTURE_SETTINGS,
            output_base=output_base,
            data_dir=data_dir,
            emit=emit,
            status=statuses.append,
            render_snapshot=False,
            render_video=True,
            pipeline_factory_cls=_FakePipelineFactory,
        )

        self.assertEqual(_FakePipelineFactory.summary, summary)
        self.assertEqual(
            [
                "Fetching runtime credentials",
                "Opening preview session",
                "Connected",
                "Starting live preview",
                "Receiving media packets",
                "Done. Video saved: video.mp4",
            ],
            statuses,
        )
        self.assertEqual(
            [
                {"connected": True},
                {"quii_setup_acked": True},
                _FakePipelineFactory.summary,
            ],
            emitted,
        )
        self.assertEqual(
            [
                "connector.fetch_credentials",
                "connector.open_preview",
                "session.enter",
                "session.connection_summary",
                "session.start_live_preview:0:1:3.0",
                "session.exit",
            ],
            events,
        )
        self.assertEqual(
            [
                "pipeline_factory.init",
                "pipeline_factory.create",
                "pipeline.capture",
            ],
            _FakePipelineFactory.events,
        )

        factory = _FakePipelineFactory.instances[0]
        self.assertIs(
            DEFAULT_PREVIEW_CAPTURE_SETTINGS,
            factory.preview_settings,
        )
        self.assertIs(emit, factory.emit)
        self.assertEqual(data_dir, factory.data_dir)
        self.assertFalse(factory.render_snapshot)
        self.assertTrue(factory.render_video)
        self.assertIs(
            connector.session.tunnel,
            factory.create_kwargs["tunnel"],
        )
        self.assertEqual("data-key", factory.create_kwargs["data_key"])
        self.assertIs(
            connector.session.credentials,
            factory.create_kwargs["credentials"],
        )
        self.assertEqual(output_base, factory.create_kwargs["output_base"])


if __name__ == "__main__":
    unittest.main()
