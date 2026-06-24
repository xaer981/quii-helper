from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quii_helper.config.constants import (
    CAMERA_APP_ID,
    CAMERA_CHANNEL,
    CAMERA_CLIENT_TYPE,
    CAMERA_OEM,
    CAMERA_STREAM,
    CLOUD_ACCOUNT,
    CLOUD_AUTH_URL,
    CLOUD_CLIENT_UUID,
    CLOUD_PASSWORD,
    CLOUD_SERVICE_URL,
    DEVICE_ID,
    IP_REGION_ID,
    TLS_CA_PATH,
    TLS_CERT_PATH,
    TLS_KEY_PATH,
)

from . import validation as _config_validation

DEFAULT_SERVICE_URL = CLOUD_SERVICE_URL
DEFAULT_AUTH_URL = CLOUD_AUTH_URL
DEFAULT_OEM = CAMERA_OEM
DEFAULT_APP_ID = CAMERA_APP_ID
DEFAULT_CLIENT_TYPE = CAMERA_CLIENT_TYPE
DEFAULT_SERVICE_QUERY_PATH = "/mst/query"
DEFAULT_CHANNEL = CAMERA_CHANNEL
DEFAULT_STREAM = CAMERA_STREAM

STREAM_HIGH_QUALITY = _config_validation.STREAM_HIGH_QUALITY
STREAM_LOW_BANDWIDTH = _config_validation.STREAM_LOW_BANDWIDTH
STREAM_QUALITY_ALIASES = _config_validation.STREAM_QUALITY_ALIASES
REQUIRED_CAMERA_APP_FIELDS = _config_validation.REQUIRED_CAMERA_APP_FIELDS
resolve_stream_quality = _config_validation.resolve_stream_quality
validate_camera_app_config = _config_validation.validate_camera_app_config


@dataclass
class RuntimeCredentials:
    session_id: str
    dynamic_password: str
    data_encode_key: str
    auth_code: str
    transparent_basedata: str
    raw: dict[str, Any]


@dataclass
class ServiceEntry:
    server_type: str
    query_result: int
    region_id: int
    url: str
    uri: str = ""
    param: str = ""


@dataclass
class ServiceQueryResponse:
    seq: int
    timestamp: int
    result: int
    client_region_id: int
    re_maxtime: int
    ip_validity: int
    servers: list[ServiceEntry]

    def find(self, server_type: str) -> ServiceEntry | None:
        for entry in self.servers:
            if entry.server_type == server_type:
                return entry
        return None


@dataclass
class AutonomousConfig:
    device_id: str = DEVICE_ID
    cloud_account: str = CLOUD_ACCOUNT
    cloud_password: str = CLOUD_PASSWORD
    channel: int = DEFAULT_CHANNEL
    stream: int = DEFAULT_STREAM
    connect_mode: int = -1
    service_url: str = DEFAULT_SERVICE_URL
    auth_url: str = DEFAULT_AUTH_URL
    oem: str = DEFAULT_OEM
    live_play_payload: str = "path"
    live_inner: bool = False
    live_newcn: bool = False
    live_keepalive_interval: float = 10.0
    play_sync_iterations: int = 0
    enable_play_probes: bool = False
    app_id: int = DEFAULT_APP_ID
    client_type: int = DEFAULT_CLIENT_TYPE
    client_id: str = CLOUD_CLIENT_UUID
    force_trans: int = 0
    ust_address: str = ""
    ust_test_address: str = ""
    ca_path: Path = TLS_CA_PATH
    cert_path: Path = TLS_CERT_PATH
    key_path: Path = TLS_KEY_PATH
    ip_region_id: int = IP_REGION_ID
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
