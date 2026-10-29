from dataclasses import dataclass, replace
from http.cookiejar import CookieJar
from threading import Event
from typing import Any, overload

from quii_helper.cloud.services.discovery import fetch_runtime_credentials
from quii_helper.config import AutonomousConfig, RuntimeCredentials
from quii_helper.config.connection import require_cloud_connection
from quii_helper.direct.preview import open_direct_preview
from quii_helper.protocols.p2p.models import (
    P2PConnectResponse,
    ParsedP2PTestResponse,
)
from quii_helper.protocols.rbudp.tunnel.session import DirectKcpQuiiTunnel
from quii_helper.protocols.tcp.live.session import LanTcpSession
from quii_helper.protocols.tcp.talk.session import LanTalkSession
from quii_helper.support.errors import ConfigurationError


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
        stop_event: Event | None = None,
    ) -> bool:
        """Start playback unless cancellation was requested between setup stages."""
        if stop_event is not None and stop_event.is_set():
            return False
        setup_acked = self.wait_setup_ack(timeout=setup_timeout)
        if stop_event is not None and stop_event.is_set():
            return False
        if not setup_acked:
            self.send_setup(seq=setup_seq)
            setup_acked = self.wait_setup_ack(timeout=setup_timeout)
        if stop_event is not None and stop_event.is_set():
            return False
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
        self.cookie_jar = CookieJar()

    def fetch_credentials(self) -> RuntimeCredentials:
        require_cloud_connection(
            self.config.connection_mode, operation="fetch_credentials"
        )
        return fetch_runtime_credentials(
            self.config, cookie_jar=self.cookie_jar
        )

    def create_lan_session(
        self, *, channel: int | None = None
    ) -> LanTcpSession:
        """Construct an unopened preview, optionally selecting another panel."""
        config = (
            self.config
            if channel is None
            else replace(self.config, channel=channel)
        )
        return LanTcpSession(config)

    def create_lan_talk_session(self) -> LanTalkSession:
        """Construct generic talk; the separate preview selects the panel."""
        return LanTalkSession(self.config)

    @overload
    def open_preview(
        self, *, credentials: RuntimeCredentials
    ) -> CameraPreviewSession: ...

    @overload
    def open_preview(
        self, *, credentials: None = None
    ) -> CameraPreviewSession | LanTcpSession: ...

    def open_preview(
        self, *, credentials: RuntimeCredentials | None = None
    ) -> CameraPreviewSession | LanTcpSession:
        if self.config.connection_mode == "lan":
            if credentials is not None:
                raise ConfigurationError(
                    "LAN-only sessions do not accept cloud credentials"
                )
            return self.create_lan_session().open()
        require_cloud_connection(
            self.config.connection_mode, operation="open_preview"
        )
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

    def connect(self) -> CameraPreviewSession | LanTcpSession:
        if self.config.connection_mode == "lan":
            return self.open_preview()
        credentials = self.fetch_credentials()
        return self.open_preview(credentials=credentials)
