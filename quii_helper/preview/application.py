from collections.abc import Callable

from quii_helper.camera import CameraConnector
from quii_helper.config import AutonomousConfig
from quii_helper.preview.config import (
    DEFAULT_PREVIEW_CAPTURE_SETTINGS,
    PreviewCaptureSettings,
)
from quii_helper.preview.pipeline_factory import PreviewPipelineFactory

EmitCallback = Callable[[object], None]
StatusCallback = Callable[[str], None]


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
        self.emit = emit or (lambda obj: None)
        self.status = status or (lambda message: None)
        self.pipeline_factory = pipeline_factory or PreviewPipelineFactory(
            preview_settings=self.preview_settings,
            emit=self.emit,
        )

    def run(self) -> dict:
        self.status("=== autonomous_preview ===")
        self.status(
            f"device_id={self.config.device_id} "
            f"channel={self.config.channel} "
            f"stream={self.config.stream}"
        )

        credentials = self.connector.fetch_credentials()
        self.status("fetched runtime credentials")

        with self.connector.open_preview(credentials=credentials) as session:
            credentials = session.credentials
            tunnel = session.tunnel
            self.status("p2pconnect ok")
            self.emit(session.connection_summary())

            session.send_setup(seq=0)
            self.status("sent quii setup")
            setup_acked = session.wait_setup_ack(timeout=3.0)
            self.emit({"quii_setup_acked": setup_acked})
            session.send_play(seq=1)
            self.status("sent quii play")

            pipeline = self.pipeline_factory.create(
                tunnel=tunnel,
                data_key=credentials.data_encode_key,
                credentials=credentials,
            )
            summary = pipeline.capture()
            self.emit(summary)
            return summary
