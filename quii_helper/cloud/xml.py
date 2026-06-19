import hashlib
import xml.etree.ElementTree as ET
from collections.abc import Callable

from quii_helper.cloud.defaults import (
    CLOUD_APP_ID,
    CLOUD_AUTH_VERSION,
    CLOUD_CLIENT_TYPE,
    CLOUD_OEM_ID,
)
from quii_helper.constants import CLOUD_CLIENT_UUID

ContentBuilder = Callable[[ET.Element], None]


def userauth_password(value: str) -> str:
    if value and len(value) != 64:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    return value or ""


def build_userauth_xml(
    command: str,
    content_builder: ContentBuilder,
    *,
    content_class: str | None = None,
    session_id: str | None = None,
    seq: int = 0,
    client_id: str | None = None,
) -> bytes:
    envelope = ET.Element("envelope")

    content_attrs = {"class": content_class} if content_class else {}
    content = ET.SubElement(envelope, "content", content_attrs)
    content_builder(content)

    header = ET.SubElement(envelope, "header")
    client = ET.SubElement(header, "client")
    ET.SubElement(client, "app").text = str(CLOUD_APP_ID)
    resolved_client_id = CLOUD_CLIENT_UUID if client_id is None else client_id
    ET.SubElement(client, "id").text = (
        f"00{CLOUD_CLIENT_TYPE}-{CLOUD_APP_ID}-{resolved_client_id}"
    )
    ET.SubElement(client, "oem").text = CLOUD_OEM_ID
    ET.SubElement(client, "type").text = str(CLOUD_CLIENT_TYPE)
    ET.SubElement(header, "command").text = command
    ET.SubElement(header, "flag").text = "tdkcloud"
    ET.SubElement(header, "seq").text = str(seq)
    if session_id:
        ET.SubElement(header, "session").text = session_id
    ET.SubElement(header, "user-data")
    ET.SubElement(header, "version").text = CLOUD_AUTH_VERSION

    xml = ET.tostring(envelope, encoding="utf-8", xml_declaration=False)
    return b'<?xml version="1.0" encoding="UTF-8"?>' + xml
