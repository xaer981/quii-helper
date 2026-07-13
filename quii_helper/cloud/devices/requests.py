import xml.etree.ElementTree as ET

from quii_helper.cloud.config.defaults import DEVICE_LIST_REQ_CLASS
from quii_helper.cloud.http.xml import build_userauth_xml
from quii_helper.config import AutonomousConfig


def build_device_list_xml(
    config: AutonomousConfig,
    *,
    session_id: str,
    count: int,
    page: int,
) -> bytes:
    """Build a native-compatible `get-device-list` userauth request."""

    def content_builder(content: ET.Element) -> None:
        ET.SubElement(content, "filter").text = ""
        ET.SubElement(content, "order").text = "0"
        ET.SubElement(content, "count").text = str(count)
        ET.SubElement(content, "page").text = str(page)
        ET.SubElement(content, "owner").text = ""

    return build_userauth_xml(
        "get-device-list",
        content_builder,
        content_class=DEVICE_LIST_REQ_CLASS,
        session_id=session_id,
        seq=0,
        client_id=config.client_id,
        oem=config.oem,
        app_id=config.app_id,
        client_type=config.client_type,
    )
