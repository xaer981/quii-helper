from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quii_helper.constants import (
    CLOUD_ACCOUNT,
    CLOUD_CLIENT_UUID,
    CLOUD_PASSWORD,
    DEVICE_ID,
)

DEFAULT_SERVICE_URL = "https://tantos.qvcloud.net:443"
DEFAULT_OEM = "G0083"
DEFAULT_APP_ID = 4083
DEFAULT_CLIENT_TYPE = 3
DEFAULT_SERVICE_QUERY_PATH = "/mst/query"


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
    channel: int = 1
    stream: int = 2
    connect_mode: int = -1
    service_url: str = DEFAULT_SERVICE_URL
    oem: str = DEFAULT_OEM
    live_play_payload: str = "path"
    live_keepalive_interval: float = 10.0
    play_sync_iterations: int = 0
    enable_play_probes: bool = False
    app_id: int = DEFAULT_APP_ID
    client_type: int = DEFAULT_CLIENT_TYPE
    client_id: str = CLOUD_CLIENT_UUID
    force_trans: int = 0
    ust_address: str = ""
    ust_test_address: str = ""
    ca_path: Path = Path(r"D:\apk\vhome\vhome_clear\assets\ca.pem")
    cert_path: Path = Path(r"D:\apk\vhome\vhome_clear\assets\client.pem")
    key_path: Path = Path(r"D:\apk\vhome\vhome_clear\assets\client.txt")
    ip_region_id: int = 6
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
