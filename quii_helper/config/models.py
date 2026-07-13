from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from quii_helper.config.settings_loader import (
    EnvironmentSettings,
    get_default_settings,
    load_environment_settings,
)

DEFAULT_SERVICE_QUERY_PATH = "/mst/query"


def _settings() -> EnvironmentSettings:
    return get_default_settings()


@dataclass
class RuntimeCredentials:
    """Runtime credentials returned by the cloud for one device session.

    Attributes:
        session_id: Cloud login session id.
        dynamic_password: Device-specific dynamic password.
        data_encode_key: Key used to decode encrypted media payloads.
        auth_code: Device auth code returned by cloud userauth.
        transparent_basedata: Opaque cloud/device metadata.
        raw: Raw cloud response fields for diagnostics.
    """

    session_id: str
    dynamic_password: str
    data_encode_key: str
    auth_code: str
    transparent_basedata: str
    raw: dict[str, Any]


@dataclass
class ServiceEntry:
    """Single service-discovery entry returned by the cloud."""

    server_type: str
    query_result: int
    region_id: int
    url: str
    uri: str = ""
    param: str = ""


@dataclass
class ServiceQueryResponse:
    """Parsed cloud service-discovery response."""

    seq: int
    timestamp: int
    result: int
    client_region_id: int
    re_maxtime: int
    ip_validity: int
    servers: list[ServiceEntry]

    def find(self, server_type: str) -> ServiceEntry | None:
        """Return the first discovered service entry with the requested type."""
        for entry in self.servers:
            if entry.server_type == server_type:
                return entry
        return None


@dataclass
class AutonomousConfig:
    """Low-level configuration used by `Camera`.

    Most users should pass overrides directly to `Camera(...)` instead of
    constructing this class manually. The dataclass remains public for advanced
    code that wants to prepare a reusable configuration object.

    Attributes:
        device_id: Camera device id.
        cloud_account: Cloud account/login.
        cloud_password: Cloud account password.
        device_host: Camera LAN IP address or hostname for local `/tdkcgi`
            read-only HTTP requests.
        auth_code: Device auth code for local `/tdkcgi` read-only HTTP
            requests.
        channel: Camera channel number.
        stream: Numeric stream selector after quality resolution.
        connect_mode: Device live-play connect mode.
        service_url: Cloud service-discovery URL.
        auth_url: Cloud user-auth URL.
        oem: Original application OEM code.
        live_play_payload: QUII live-play payload mode.
        live_inner: Whether to use the inner live-play packet variant.
        live_newcn: Whether to use the new connection flag in live-play.
        live_keepalive_interval: Seconds between live keepalive packets.
        play_sync_iterations: Number of extra post-play sync iterations.
        enable_play_probes: Whether to send additional play probe packets.
        app_id: Original application id.
        client_type: Original application client type.
        client_id: Client UUID used for cloud, UST, and MQTT requests.
        force_trans: Force relay/transport mode flag used in P2P requests.
        ust_address: MQTT/UST broker address discovered from cloud services.
        ust_test_address: Optional test MQTT/UST broker address.
        ca_path: TLS CA certificate path.
        cert_path: TLS client certificate path.
        key_path: TLS client private key path.
        ip_region_id: Cloud login IP region id.
        mqtt_timeout: Seconds to wait for MQTT connection.
        prewarm_timeout: Seconds to wait for device online prewarm.
        prewarm_retry_interval: Seconds between prewarm retries.
        preconnect_settle_delay: Delay before UDP peer probing.
        preconnect_mode: Whether to run the preconnect flow.
        udp_timeout: UDP probe timeout in seconds.
        connect_timeout: General cloud/device connection timeout.
        p2pconnect_retries: Number of P2P connect request attempts.
        logical_channel: RBUDP logical channel.
        logical_conn_type: RBUDP logical connection type.
        logical_src_id_base: First RBUDP logical source id.
        logical_src_id_count: Number of RBUDP logical lanes.
        rng_seed: Optional deterministic random seed for diagnostics.
        session_flag_server_ip: Optional session flag IP override.
        session_flag_server_port: Optional session flag port override.
        mqtt_userdata: Optional MQTT userdata field.
        mqtt_client_id: Optional MQTT client id override.
        mqtt_will_topic: Optional MQTT last-will topic.
        mqtt_will_message: Optional MQTT last-will message.
        log_peer_diagnostics: Whether to log peer selection diagnostics.
        rbudp_debug: Whether to enable verbose RBUDP debug logging.
        tls_verify: Whether cloud/device HTTPS certificate verification is
            enabled. Set to `False` only for vendor endpoints with non-public
            or hostname-mismatched certificates.
    """

    device_id: str = field(default_factory=lambda: _settings().device_id)
    cloud_account: str = field(
        default_factory=lambda: _settings().cloud_account
    )
    cloud_password: str = field(
        default_factory=lambda: _settings().cloud_password
    )
    device_host: str = field(
        default_factory=lambda: _settings().camera_device_host
    )
    auth_code: str = field(default_factory=lambda: _settings().auth_code)
    channel: int = field(default_factory=lambda: _settings().camera_channel)
    stream: int = field(default_factory=lambda: _settings().camera_stream)
    connect_mode: int = -1
    service_url: str = field(
        default_factory=lambda: _settings().cloud_service_url
    )
    auth_url: str = field(default_factory=lambda: _settings().cloud_auth_url)
    oem: str = field(default_factory=lambda: _settings().camera_oem)
    live_play_payload: str = "path"
    live_inner: bool = False
    live_newcn: bool = False
    live_keepalive_interval: float = 10.0
    play_sync_iterations: int = 0
    enable_play_probes: bool = False
    app_id: int = field(default_factory=lambda: _settings().camera_app_id)
    client_type: int = field(
        default_factory=lambda: _settings().camera_client_type
    )
    client_id: str = field(
        default_factory=lambda: _settings().cloud_client_uuid
    )
    force_trans: int = 0
    ust_address: str = ""
    ust_test_address: str = ""
    ca_path: Path = field(default_factory=lambda: _settings().tls_ca_path)
    cert_path: Path = field(default_factory=lambda: _settings().tls_cert_path)
    key_path: Path = field(default_factory=lambda: _settings().tls_key_path)
    ip_region_id: int = field(default_factory=lambda: _settings().ip_region_id)
    mqtt_timeout: float = 20.0
    prewarm_timeout: float = 12.0
    prewarm_retry_interval: float = 2.0
    preconnect_settle_delay: float = 4.0
    preconnect_mode: bool = True
    udp_timeout: float = 5.0
    connect_timeout: float = 15.0
    p2pconnect_retries: int = 4
    logical_channel: int = 0
    logical_conn_type: int = 0
    logical_src_id_base: int = 0x04000006
    logical_src_id_count: int = 1
    rng_seed: int | None = None
    session_flag_server_ip: str | None = None
    session_flag_server_port: int | None = None
    mqtt_userdata: str | None = None
    mqtt_client_id: str | None = None
    mqtt_will_topic: str | None = None
    mqtt_will_message: str | None = None
    log_peer_diagnostics: bool = True
    rbudp_debug: bool = False
    tls_verify: bool = field(default_factory=lambda: _settings().tls_verify)

    @classmethod
    def from_settings(
        cls, settings: EnvironmentSettings, **overrides: object
    ) -> "AutonomousConfig":
        """Build a config from explicit loaded settings."""

        values: dict[str, object] = {
            "device_id": settings.device_id,
            "cloud_account": settings.cloud_account,
            "cloud_password": settings.cloud_password,
            "device_host": settings.camera_device_host,
            "auth_code": settings.auth_code,
            "channel": settings.camera_channel,
            "stream": settings.camera_stream,
            "service_url": settings.cloud_service_url,
            "auth_url": settings.cloud_auth_url,
            "oem": settings.camera_oem,
            "app_id": settings.camera_app_id,
            "client_type": settings.camera_client_type,
            "client_id": settings.cloud_client_uuid,
            "ca_path": settings.tls_ca_path,
            "cert_path": settings.tls_cert_path,
            "key_path": settings.tls_key_path,
            "ip_region_id": settings.ip_region_id,
            "tls_verify": settings.tls_verify,
        }
        values.update(overrides)
        return cls(**cast(Any, values))


def load_config(
    *,
    project_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    load_env_file: bool = True,
    **overrides: object,
) -> AutonomousConfig:
    """Load an `AutonomousConfig` from explicit environment settings."""

    settings = load_environment_settings(
        project_root=project_root,
        env=env,
        load_env_file=load_env_file,
    )
    return AutonomousConfig.from_settings(settings, **overrides)
