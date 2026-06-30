from collections.abc import Callable
from pathlib import Path
from typing import Any

from quii_helper.camera.outputs.results import capture_done_message
from quii_helper.models.capture import CaptureSummary
from quii_helper.preview.pipeline.config import PreviewCaptureSettings
from quii_helper.preview.pipeline.factory import PreviewPipelineFactory

EmitCallback = Callable[[object], None]
StatusCallback = Callable[[str], None]

STATUS_FETCHING_CREDENTIALS = "Fetching runtime credentials"
STATUS_OPENING_PREVIEW = "Opening preview session"
STATUS_CONNECTED = "Connected"
STATUS_STARTING_LIVE_PREVIEW = "Starting live preview"
STATUS_RECEIVING_MEDIA = "Receiving media packets"
LIVE_PREVIEW_SETUP_SEQ = 0
LIVE_PREVIEW_PLAY_SEQ = 1
LIVE_PREVIEW_SETUP_TIMEOUT_SECONDS = 3.0


def capture_preview_summary(
    *,
    connector: Any,
    settings: PreviewCaptureSettings,
    output_base: Path | None,
    data_dir: Path,
    emit: EmitCallback,
    status: StatusCallback,
    render_snapshot: bool,
    render_video: bool,
    pipeline_factory_cls: type[PreviewPipelineFactory] = (
        PreviewPipelineFactory
    ),
) -> CaptureSummary:
    status(STATUS_FETCHING_CREDENTIALS)
    credentials = connector.fetch_credentials()
    status(STATUS_OPENING_PREVIEW)
    with connector.open_preview(credentials=credentials) as session:
        status(STATUS_CONNECTED)
        emit(session.connection_summary())
        status(STATUS_STARTING_LIVE_PREVIEW)
        setup_acked = session.start_live_preview(
            setup_seq=LIVE_PREVIEW_SETUP_SEQ,
            play_seq=LIVE_PREVIEW_PLAY_SEQ,
            setup_timeout=LIVE_PREVIEW_SETUP_TIMEOUT_SECONDS,
        )
        emit({"quii_setup_acked": setup_acked})
        status(STATUS_RECEIVING_MEDIA)
        pipeline = pipeline_factory_cls(
            preview_settings=settings,
            emit=emit,
            data_dir=data_dir,
            render_snapshot=render_snapshot,
            render_video=render_video,
        ).create(
            tunnel=session.tunnel,
            data_key=session.credentials.data_encode_key,
            credentials=session.credentials,
            output_base=output_base,
        )
        summary = pipeline.capture()
        emit(summary)
        status(capture_done_message(summary))
        return summary
