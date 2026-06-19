from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from quii_helper.cloud.service_discovery import fetch_runtime_credentials
from quii_helper.config import AutonomousConfig, RuntimeCredentials
from quii_helper.direct.preview import open_direct_preview
from quii_helper.io.paths import DATA_DIR
from quii_helper.preview.config import (
    DEFAULT_PREVIEW_CAPTURE_SETTINGS,
    PreviewCaptureSettings,
)
from quii_helper.preview.pipeline_factory import PreviewPipelineFactory
from quii_helper.protocols.p2p.models import (
    P2PConnectResponse,
    ParsedP2PTestResponse,
)
from quii_helper.protocols.rbudp.tunnel import DirectKcpQuiiTunnel

EmitCallback = Callable[[object], None]
StatusCallback = Callable[[str], None]


class CameraCaptureError(RuntimeError):
    """Raised when a requested media artifact could not be produced."""


@dataclass(frozen=True)
class CameraCaptureResult:
    summary: dict
    snapshot_path: Path | None
    video_path: Path | None
    snapshot_written: bool
    video_written: bool
    media_written: bool

    @classmethod
    def from_summary(cls, summary: dict) -> "CameraCaptureResult":
        artifact = (
            summary.get("media_result")
            or summary.get("embedded_fallback")
            or {}
        )
        snapshot_path = _optional_path(artifact.get("snapshot_path"))
        video_path = _optional_path(artifact.get("mp4_path"))
        return cls(
            summary=summary,
            snapshot_path=snapshot_path,
            video_path=video_path,
            snapshot_written=bool(artifact.get("snapshot"))
            and snapshot_path is not None,
            video_written=bool(artifact.get("mp4")) and video_path is not None,
            media_written=bool(artifact.get("written")),
        )

    def require_snapshot(self) -> Path:
        if self.snapshot_written and self.snapshot_path is not None:
            return self.snapshot_path
        raise CameraCaptureError(
            "snapshot was not produced; "
            "inspect CameraCaptureResult.summary for details"
        )

    def require_video(self) -> Path:
        if self.video_written and self.video_path is not None:
            return self.video_path
        raise CameraCaptureError(
            "video was not produced; "
            "inspect CameraCaptureResult.summary for details"
        )


def _optional_path(value: object) -> Path | None:
    if not value:
        return None
    return Path(str(value))


@dataclass
class CameraPreviewSession:
    config: AutonomousConfig
    credentials: RuntimeCredentials
    response: P2PConnectResponse
    test_response: ParsedP2PTestResponse
    tunnel: DirectKcpQuiiTunnel

    def connection_summary(self) -> dict[str, Any]:
        return {
            "public_ip": self.response.public_ip,
            "public_udp_port": self.response.public_udp_port,
            "utd_public_ip": self.response.utd_public_ip,
            "utd_public_udp_port": self.response.utd_public_udp_port,
            "response_local_ips": self.response.local_ips,
            "response_local_udp_port": self.response.local_udp_port,
            "test_peer": (
                f"{self.test_response.address}:{self.test_response.port}"
            ),
            "test_id": self.test_response.test_id,
            "transport_peer": (
                f"{self.tunnel.transport_peer_addr[0]}:"
                f"{self.tunnel.transport_peer_addr[1]}"
            ),
            "logic_peer": (
                f"{self.tunnel.peer_addr[0]}:{self.tunnel.peer_addr[1]}"
            ),
            "rbudp_local_id": self.tunnel.local_id,
            "rbudp_remote_id": self.tunnel.remote_id,
            "rbudp_word4": hex(self.tunnel.word4),
            "rbudp_word8": hex(self.tunnel.word8),
            "dest_id": self.tunnel.dest_id,
        }

    def send_setup(self, *, seq: int = 0) -> None:
        self.tunnel.send_quii_setup(seq=seq)

    def wait_setup_ack(self, *, timeout: float = 3.0) -> bool:
        return self.tunnel.wait_quii_setup_ack(timeout=timeout)

    def send_play(self, *, seq: int = 1) -> None:
        self.tunnel.send_quii_play(self.credentials, seq=seq)

    def start_live_preview(
        self,
        *,
        setup_seq: int = 0,
        play_seq: int = 1,
        setup_timeout: float = 3.0,
    ) -> bool:
        setup_acked = self.wait_setup_ack(timeout=setup_timeout)
        if not setup_acked:
            self.send_setup(seq=setup_seq)
            setup_acked = self.wait_setup_ack(timeout=setup_timeout)
        self.send_play(seq=play_seq)
        return setup_acked

    def close(self) -> None:
        self.tunnel.close()

    def __enter__(self) -> "CameraPreviewSession":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


class CameraConnector:
    def __init__(self, config: AutonomousConfig) -> None:
        self.config = config

    def fetch_credentials(self) -> RuntimeCredentials:
        return fetch_runtime_credentials(self.config)

    def open_preview(
        self, *, credentials: RuntimeCredentials | None = None
    ) -> CameraPreviewSession:
        resolved_credentials, response, test_response, tunnel = (
            open_direct_preview(
                self.config,
                credentials=credentials,
            )
        )
        return CameraPreviewSession(
            config=self.config,
            credentials=resolved_credentials,
            response=response,
            test_response=test_response,
            tunnel=tunnel,
        )

    def connect(self) -> CameraPreviewSession:
        credentials = self.fetch_credentials()
        return self.open_preview(credentials=credentials)


class Camera:
    def __init__(
        self,
        config: AutonomousConfig | None = None,
        *,
        device_id: str | None = None,
        cloud_account: str | None = None,
        cloud_password: str | None = None,
        client_id: str | None = None,
        live_play_payload: str | None = None,
        live_keepalive_interval: float | None = None,
        play_sync_iterations: int | None = None,
        enable_play_probes: bool | None = None,
        channel: int | None = None,
        stream: int | None = None,
        preview_settings: PreviewCaptureSettings | None = None,
        data_dir: str | Path = DATA_DIR,
        emit: EmitCallback | None = None,
        status: StatusCallback | None = None,
    ) -> None:
        self.config = self._resolve_config(
            config or AutonomousConfig(),
            device_id=device_id,
            cloud_account=cloud_account,
            cloud_password=cloud_password,
            client_id=client_id,
            live_play_payload=live_play_payload,
            live_keepalive_interval=live_keepalive_interval,
            play_sync_iterations=play_sync_iterations,
            enable_play_probes=enable_play_probes,
            channel=channel,
            stream=stream,
        )
        self.preview_settings = (
            preview_settings or DEFAULT_PREVIEW_CAPTURE_SETTINGS
        )
        self.data_dir = Path(data_dir)
        self.emit = emit or (lambda obj: None)
        self.status = status or (lambda message: None)
        self.connector = CameraConnector(self.config)

    def capture(
        self,
        *,
        duration_seconds: float | None = None,
        output_path: str | Path | None = None,
        save_diagnostic_artifacts: bool | None = None,
        stop_when_decodable: bool | None = None,
        render_snapshot: bool = True,
        render_video: bool = True,
    ) -> CameraCaptureResult:
        settings = self._capture_settings(
            duration_seconds=duration_seconds,
            save_diagnostic_artifacts=save_diagnostic_artifacts,
            stop_when_decodable=stop_when_decodable,
        )
        output_base = self._output_base_from_path(output_path)
        summary = self._capture_summary(
            settings=settings,
            output_base=output_base,
            render_snapshot=render_snapshot,
            render_video=render_video,
        )
        return CameraCaptureResult.from_summary(summary)

    def snapshot(
        self,
        *,
        timeout_seconds: float = 5.0,
        output_path: str | Path | None = None,
    ) -> Path:
        result = self.capture(
            duration_seconds=timeout_seconds,
            output_path=self._validate_output_path(output_path, ".jpg"),
            stop_when_decodable=True,
            render_snapshot=True,
            render_video=False,
        )
        return result.require_snapshot()

    def save_video(
        self,
        duration_seconds: float,
        *,
        output_path: str | Path | None = None,
    ) -> Path:
        result = self.capture(
            duration_seconds=duration_seconds,
            output_path=self._validate_output_path(output_path, ".mp4"),
            stop_when_decodable=False,
            render_snapshot=False,
            render_video=True,
        )
        return result.require_video()

    def record(
        self,
        duration_seconds: float,
        *,
        output_path: str | Path | None = None,
    ) -> Path:
        return self.save_video(duration_seconds, output_path=output_path)

    def _capture_summary(
        self,
        *,
        settings: PreviewCaptureSettings,
        output_base: Path | None,
        render_snapshot: bool,
        render_video: bool,
    ) -> dict:
        self.status("fetching runtime credentials")
        credentials = self.connector.fetch_credentials()
        self.status("opening preview session")
        with self.connector.open_preview(credentials=credentials) as session:
            self.emit(session.connection_summary())
            self.status("starting live preview")
            setup_acked = session.start_live_preview(
                setup_seq=0, play_seq=1, setup_timeout=3.0
            )
            self.emit({"quii_setup_acked": setup_acked})
            pipeline = PreviewPipelineFactory(
                preview_settings=settings,
                emit=self.emit,
                data_dir=self.data_dir,
                render_snapshot=render_snapshot,
                render_video=render_video,
            ).create(
                tunnel=session.tunnel,
                data_key=session.credentials.data_encode_key,
                credentials=session.credentials,
                output_base=output_base,
            )
            summary = pipeline.capture()
            self.emit(summary)
            return summary

    def _capture_settings(
        self,
        *,
        duration_seconds: float | None,
        save_diagnostic_artifacts: bool | None,
        stop_when_decodable: bool | None,
    ) -> PreviewCaptureSettings:
        values: dict[str, Any] = {}
        if duration_seconds is not None:
            if duration_seconds <= 0:
                raise ValueError("duration_seconds must be greater than zero")
            values["capture_seconds"] = float(duration_seconds)
        if save_diagnostic_artifacts is not None:
            values["save_diagnostic_artifacts"] = bool(
                save_diagnostic_artifacts
            )
        if stop_when_decodable is not None:
            values["stop_when_decodable"] = bool(stop_when_decodable)
        return (
            replace(self.preview_settings, **values)
            if values
            else self.preview_settings
        )

    @staticmethod
    def _resolve_config(
        config: AutonomousConfig,
        *,
        device_id: str | None,
        cloud_account: str | None,
        cloud_password: str | None,
        client_id: str | None,
        live_play_payload: str | None,
        live_keepalive_interval: float | None,
        play_sync_iterations: int | None,
        enable_play_probes: bool | None,
        channel: int | None,
        stream: int | None,
    ) -> AutonomousConfig:
        values: dict[str, Any] = {}
        if device_id is not None:
            values["device_id"] = device_id
        if cloud_account is not None:
            values["cloud_account"] = cloud_account
        if cloud_password is not None:
            values["cloud_password"] = cloud_password
        if client_id is not None:
            values["client_id"] = client_id
        if live_play_payload is not None:
            values["live_play_payload"] = live_play_payload
        if live_keepalive_interval is not None:
            if live_keepalive_interval < 0:
                raise ValueError(
                    "live_keepalive_interval must be zero or greater"
                )
            values["live_keepalive_interval"] = float(live_keepalive_interval)
        if play_sync_iterations is not None:
            if play_sync_iterations < 0:
                raise ValueError(
                    "play_sync_iterations must be zero or greater"
                )
            values["play_sync_iterations"] = play_sync_iterations
        if enable_play_probes is not None:
            values["enable_play_probes"] = bool(enable_play_probes)
        if channel is not None:
            values["channel"] = channel
        if stream is not None:
            values["stream"] = stream
        return replace(config, **values) if values else config

    @staticmethod
    def _validate_output_path(
        output_path: str | Path | None, expected_suffix: str
    ) -> Path | None:
        if output_path is None:
            return None
        path = Path(output_path)
        if path.suffix and path.suffix.lower() != expected_suffix:
            raise ValueError(f"output_path must use {expected_suffix} suffix")
        return path

    @staticmethod
    def _output_base_from_path(output_path: str | Path | None) -> Path | None:
        if output_path is None:
            return None
        path = Path(output_path)
        return path.with_suffix("") if path.suffix else path
