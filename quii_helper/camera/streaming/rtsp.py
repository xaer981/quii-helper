from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from quii_helper.preview.outputs.manager.artifacts import (
    PreviewArtifactManager,
)
from quii_helper.preview.pipeline.config import PreviewCaptureSettings
from quii_helper.preview.pipeline.stream import TunnelPacketStream
from quii_helper.preview.processing.packets.processor import (
    PreviewPacketProcessor,
)
from quii_helper.streaming.h264 import H264LiveAssembler
from quii_helper.streaming.rtsp import RtspH264Server

STREAM_PACKET_BATCH_SECONDS = 1.0
STREAM_PACKET_TIMEOUT_SECONDS = 1.0
LIVE_PREVIEW_SETUP_SEQ = 0
LIVE_PREVIEW_PLAY_SEQ = 1
LIVE_PREVIEW_SETUP_TIMEOUT_SECONDS = 3.0
EmitCallback = Callable[[object], None]
StatusCallback = Callable[[str], None]


@dataclass
class CameraRtspStream:
    """Running RTSP stream created by `Camera.serve_rtsp()`.

    The object starts an RTSP server
    and a background producer thread that reads camera preview packets,
    assembles H.264 access units, and publishes them to RTSP clients.

    Attributes:
        connector: Camera connector used to fetch credentials and open preview.
        preview_settings: Capture/packet processing settings.
        data_dir: Directory used for temporary artifact manager state.
        emit: Callback for structured debug summaries.
        status: Callback for user-facing status messages.
        host: Interface bound by the RTSP server.
        port: TCP port bound by the RTSP server.
        path: RTSP path exposed by the server.
    """

    connector: Any
    preview_settings: PreviewCaptureSettings
    data_dir: Path
    emit: EmitCallback
    status: StatusCallback
    host: str = "0.0.0.0"
    port: int = 8554
    path: str = "/live"
    server: RtspH264Server = field(init=False)
    assembler: H264LiveAssembler = field(init=False)
    _stop_event: threading.Event = field(
        default_factory=threading.Event, init=False, repr=False
    )
    _thread: threading.Thread | None = field(default=None, init=False)
    _packet_stream: TunnelPacketStream | None = field(
        default=None, init=False, repr=False
    )
    _error: BaseException | None = field(default=None, init=False, repr=False)
    _started: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self.server = RtspH264Server(
            host=self.host,
            port=self.port,
            path=self.path,
        )
        self.assembler = H264LiveAssembler(sink=self.server.publish)

    @property
    def url(self) -> str:
        """RTSP URL clients should open."""
        return self.server.url

    @property
    def stats(self) -> dict:
        """Runtime stream statistics for diagnostics."""
        return {
            "rtsp_clients": self.server.client_count,
            "h264": self.assembler.stats,
        }

    def start(self) -> "CameraRtspStream":
        """Start the RTSP server and background camera producer.

        Returns:
            This stream handle, allowing `Camera.serve_rtsp()` to return a
            started object directly.
        """
        if self._started:
            return self
        self.status("Starting RTSP server")
        self._error = None
        self.server.start()
        self.status(f"RTSP stream ready: {self.url}")
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_preview_loop,
            name="quii-camera-rtsp-producer",
            daemon=True,
        )
        self._thread.start()
        self._started = True
        return self

    def wait(self, timeout: float | None = None) -> None:
        """Wait for the producer thread and re-raise producer errors.

        Args:
            timeout: Maximum seconds to wait. `None` waits indefinitely.

        Raises:
            BaseException: Re-raises the background producer error, if any.
        """
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        if self._error is not None:
            raise self._error

    def close(self) -> None:
        """
        Stop the producer, close the packet stream, and stop RTSP serving.
        """
        self._stop_event.set()
        if self._packet_stream is not None:
            self._packet_stream.close()
        self.server.close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._started = False

    def __enter__(self) -> "CameraRtspStream":
        """Start and return this stream when used as a context manager."""
        return self.start()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Close the stream when leaving a context manager block."""
        self.close()

    def _run_preview_loop(self) -> None:
        try:
            self.status("Fetching runtime credentials")
            credentials = self.connector.fetch_credentials()
            self.status("Opening preview session")
            with self.connector.open_preview(
                credentials=credentials
            ) as session:
                self.status("Connected")
                self.emit(session.connection_summary())
                self.status("Starting live preview")
                setup_acked = session.start_live_preview(
                    setup_seq=LIVE_PREVIEW_SETUP_SEQ,
                    play_seq=LIVE_PREVIEW_PLAY_SEQ,
                    setup_timeout=LIVE_PREVIEW_SETUP_TIMEOUT_SECONDS,
                )
                self.emit({"quii_setup_acked": setup_acked})
                self.status("Receiving media packets")
                self._consume_session_packets(session, credentials)
        except Exception as exc:
            if self._stop_event.is_set():
                return
            self._error = exc
            self.status(f"RTSP producer stopped: {exc}")

    def _consume_session_packets(self, session: Any, credentials: Any) -> None:
        artifacts = PreviewArtifactManager(
            diagnostics_enabled=False,
            data_dir=self.data_dir,
            direct_blob_sample_limit=(
                self.preview_settings.direct_blob_sample_limit
            ),
            wrapped_tail_sample_limit=(
                self.preview_settings.wrapped_tail_sample_limit
            ),
            fragment_partial_sample_limit=(
                self.preview_settings.fragment_partial_sample_limit
            ),
        )
        processor = PreviewPacketProcessor(
            key=session.credentials.data_encode_key,
            artifacts=artifacts,
            fragment_partial_collector=(
                artifacts.create_fragment_partial_collector(
                    key=session.credentials.data_encode_key
                )
            ),
            emit=self.emit,
            min_media_messages=self.preview_settings.min_media_messages,
            max_media_messages=self.preview_settings.max_media_messages,
            direct_blob_summary_limit=(
                self.preview_settings.direct_blob_summary_limit
            ),
            media_message_sink=self.assembler.feed_message,
            store_media_messages=False,
        )
        self._packet_stream = TunnelPacketStream(session.tunnel)
        while not self._stop_event.is_set():
            for packet in self._packet_stream.live_packets(
                duration=STREAM_PACKET_BATCH_SECONDS,
                timeout=STREAM_PACKET_TIMEOUT_SECONDS,
                keepalive_credentials=credentials,
            ):
                if self._stop_event.is_set():
                    break
                processor.process_packet(packet, phase="live")
