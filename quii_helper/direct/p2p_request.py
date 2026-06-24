import random
import time

from quii_helper.config import AutonomousConfig, RuntimeCredentials
from quii_helper.protocols.p2p.messages.session import create_session_flag
from quii_helper.protocols.p2p.models import P2PConnectRequest


def create_direct_session_flag(
    config: AutonomousConfig,
    request_counter: int,
    *,
    rng: random.Random,
) -> str:
    if (
        config.session_flag_server_ip
        and config.session_flag_server_port is not None
    ):
        return create_session_flag(
            config.session_flag_server_ip,
            config.session_flag_server_port,
            request_counter,
            config.device_id,
            rng=rng,
        )
    return f"{rng.randrange(0x100000000):08x}{int(time.time())}"


def build_direct_p2pconnect_request(
    *,
    config: AutonomousConfig,
    credentials: RuntimeCredentials,
    session_flag: str,
    request_session_id: int,
) -> P2PConnectRequest:
    return P2PConnectRequest(
        client_id=config.client_id
        or credentials.raw["login"].get("client_id", "")
        or "",
        client_type=config.client_type,
        oem=config.oem,
        app=config.app_id,
        device_id=config.device_id,
        session_flag=session_flag,
        request_session_id=request_session_id,
        mon_channel=-1,
        force_trans=config.force_trans,
        dev_type="normal",
        dev_sub_state="awakened",
        userdata=config.mqtt_userdata,
    )
