from quii_helper.protocols.ust.message_builder import (
    build_ust_header,
    dump_ust_payload,
)


def build_ust_register_request(
    *,
    client_id: str,
    client_type: str | int,
    oem: str,
    app: str | int,
    version: str = "v3.2.0",
    flag: str = "tdkcloud",
    userdata: str | None = None,
    seq: str | None = None,
    session: str | None = None,
) -> str:
    """
    Reimplementation of AppClientUst::CreateRegisterMsg() +
    RequMsgHeader::BuildJson().
    """
    header = build_ust_header(
        command="register",
        client_id=client_id,
        client_type=client_type,
        oem=oem,
        app=app,
        version=version,
        flag=flag,
        userdata=userdata,
        seq=seq,
        session=session,
    )
    return dump_ust_payload({"header": header})


def build_ust_unregister_request(
    *,
    client_id: str,
    version: str = "v3.2.0",
    flag: str = "tdkcloud",
    userdata: str | None = None,
) -> str:
    header = build_ust_header(
        command="unregister",
        client_id=client_id,
        version=version,
        flag=flag,
        userdata=userdata,
    )
    return dump_ust_payload({"header": header})


def build_ust_sub_device_state_request(
    *,
    client_id: str,
    client_type: str | int,
    oem: str,
    app: str | int,
    device_ids: list[str],
    version: str = "v3.2.0",
    flag: str = "tdkcloud",
    userdata: str | None = None,
) -> str:
    header = build_ust_header(
        command="sub-device-state",
        client_id=client_id,
        client_type=client_type,
        oem=oem,
        app=app,
        version=version,
        flag=flag,
        userdata=userdata,
    )
    payload = {
        "header": header,
        "content": {
            "devid": device_ids,
        },
    }
    return dump_ust_payload(payload)


def build_ust_update_netinfo_request(
    *,
    client_id: str,
    client_type: str | int,
    oem: str,
    app: str | int,
    public_ip: str,
    public_udp_port: int,
    local_ips: list[str],
    local_udp_port: int,
    nettype: int = 4,
    netsubtype: int = 0,
    version: str = "v3.2.0",
    flag: str = "tdkcloud",
    userdata: str | None = None,
) -> str:
    header = build_ust_header(
        command="update-netinfo",
        client_id=client_id,
        client_type=client_type,
        oem=oem,
        app=app,
        version=version,
        flag=flag,
        userdata=userdata,
    )
    payload = {
        "header": header,
        "content": {
            "nettype": nettype,
            "netsubtype": netsubtype,
            "pub-ip": public_ip,
            "pub-udpport": public_udp_port,
            "loc-ip": local_ips,
            "loc-udp-port": local_udp_port,
        },
    }
    return dump_ust_payload(payload)
