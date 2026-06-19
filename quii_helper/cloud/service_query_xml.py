from quii_helper.config import AutonomousConfig


def build_service_query_xml(
    config: AutonomousConfig,
    *,
    seq: int,
    server_types: tuple[str, ...],
) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<envelope><header>"
        "<flag>tdkcloud</flag>"
        "<command>query-hlrv2</command>"
        f"<seq>{seq}</seq>"
        "</header><content>"
        f"<server-type>{','.join(server_types)}</server-type>"
        f"<oem>{config.oem}</oem>"
        "<devid></devid>"
        "<public-ip></public-ip>"
        f"<client-id>{config.client_id}</client-id>"
        f"<regionid>{config.ip_region_id}</regionid>"
        "<version>4456</version>"
        "</content></envelope>"
    ).encode("utf-8")
