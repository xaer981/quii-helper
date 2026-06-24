from collections.abc import Callable

from quii_helper.camera import CameraConnector
from quii_helper.config import AutonomousConfig
from quii_helper.preview.pipeline.config import (
    DEFAULT_PREVIEW_CAPTURE_SETTINGS,
    PreviewCaptureSettings,
)
from quii_helper.preview.pipeline.factory import PreviewPipelineFactory
from quii_helper.support.log import logger

EmitCallback = Callable[[object], None]
StatusCallback = Callable[[str], None]


def _default_emit(obj: object) -> None:
    logger.debug("{}", obj)


def _default_status(message: str) -> None:
    logger.info(message)


class CameraPreviewApplication:
    def __init__(
        self,
        *,
        config: AutonomousConfig | None = None,
        preview_settings: PreviewCaptureSettings | None = None,
        connector: CameraConnector | None = None,
        pipeline_factory: PreviewPipelineFactory | None = None,
        emit: EmitCallback | None = None,
        status: StatusCallback | None = None,
    ) -> None:
        self.config = config or AutonomousConfig()
        self.preview_settings = (
            preview_settings or DEFAULT_PREVIEW_CAPTURE_SETTINGS
        )
        self.connector = connector or CameraConnector(self.config)
        self.emit = emit or _default_emit
        self.status = status or _default_status
        self.pipeline_factory = pipeline_factory or PreviewPipelineFactory(
            preview_settings=self.preview_settings,
            emit=self.emit,
        )

    def run(self) -> dict:
        self.status("Starting camera preview")
        self.status(
            f"Device {self.config.device_id}; "
            f"channel {self.config.channel}; "
            f"stream {self.config.stream}"
        )

        credentials = self.connector.fetch_credentials()
        self.status("Fetched runtime credentials")

        with self.connector.open_preview(credentials=credentials) as session:
            credentials = session.credentials
            tunnel = session.tunnel
            self.status("Connected")
            self.emit(session.connection_summary())

            session.send_setup(seq=0)
            self.status("Starting live preview")
            setup_acked = session.wait_setup_ack(timeout=3.0)
            self.emit({"quii_setup_acked": setup_acked})
            session.send_play(seq=1)
            self.status("Receiving media packets")

            pipeline = self.pipeline_factory.create(
                tunnel=tunnel,
                data_key=credentials.data_encode_key,
                credentials=credentials,
            )
            summary = pipeline.capture()
            self.emit(summary)
            self.status("Done")
            return summary


__all__ = ["CameraPreviewApplication"]
