import random
from dataclasses import dataclass

from quii_helper.config import AutonomousConfig, RuntimeCredentials
from quii_helper.direct.p2p_mqtt import run_mqtt_p2pconnect_attempt
from quii_helper.direct.p2p_request import (
    build_direct_p2pconnect_request,
    create_direct_session_flag,
)
from quii_helper.protocols.mqtt.bootstrap import MqttP2PBootstrap
from quii_helper.protocols.mqtt.runtime import (
    ensure_mqtt_runtime,
    reset_mqtt_runtime,
)
from quii_helper.protocols.p2p.models import P2PConnectResponse
from quii_helper.protocols.p2p.session import create_request_session_id


@dataclass(frozen=True)
class DirectP2PConnectSession:
    response: P2PConnectResponse
    request_session_id: int
    session_flag: str


def establish_direct_p2pconnect_session(
    *,
    config: AutonomousConfig,
    credentials: RuntimeCredentials,
    rng: random.Random,
    public_ip: str,
    public_udp_port: int,
    local_ips: list[str],
    local_udp_port: int,
) -> DirectP2PConnectSession:
    last_mqtt_exc: Exception | None = None

    for attempt_index in range(config.p2pconnect_retries):
        request_counter = rng.randrange(0x10000)
        request_session_id = create_request_session_id(
            request_counter, rng=rng
        )
        session_flag = create_direct_session_flag(
            config, request_counter, rng=rng
        )
        request = build_direct_p2pconnect_request(
            config=config,
            credentials=credentials,
            session_flag=session_flag,
            request_session_id=request_session_id,
        )

        reset_mqtt_runtime(config)
        ensure_mqtt_runtime(config)
        mqtt_bootstrap = MqttP2PBootstrap(config)
        try:
            response = run_mqtt_p2pconnect_attempt(
                mqtt_bootstrap,
                config=config,
                request=request,
                session_flag=session_flag,
                public_ip=public_ip,
                public_udp_port=public_udp_port,
                local_ips=local_ips,
                local_udp_port=local_udp_port,
                attempt_index=attempt_index,
            )
            return DirectP2PConnectSession(
                response=response,
                request_session_id=request_session_id,
                session_flag=session_flag,
            )
        except Exception as exc:
            last_mqtt_exc = exc
        finally:
            mqtt_bootstrap.close()

    if last_mqtt_exc is not None:
        raise last_mqtt_exc
    raise RuntimeError("failed to establish p2pconnect session")
