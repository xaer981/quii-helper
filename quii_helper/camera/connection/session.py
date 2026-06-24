from dataclasses import dataclass
from typing import Any

from quii_helper.cloud.services.discovery import fetch_runtime_credentials
from quii_helper.config import AutonomousConfig, RuntimeCredentials
from quii_helper.direct.preview import open_direct_preview
from quii_helper.protocols.p2p.models import (
    P2PConnectResponse,
    ParsedP2PTestResponse,
)
from quii_helper.protocols.rbudp.tunnel.session import DirectKcpQuiiTunnel


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
