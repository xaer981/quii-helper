import hashlib
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import cast

from quii_helper.cloud.config.defaults import CLOUD_AUTH_VERSION

ContentBuilder = Callable[[ET.Element], None]


def userauth_password(value: str) -> str:
    if value and len(value) != 64:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    return value or ""


def build_userauth_xml(
    command: str,
    content_builder: ContentBuilder,
    *,
    client_id: str,
    oem: str,
    app_id: int,
    client_type: int,
    content_class: str | None = None,
    session_id: str | None = None,
    seq: int = 0,
) -> bytes:
    envelope = ET.Element("envelope")

    content_attrs = {"class": content_class} if content_class else {}
    content = ET.SubElement(envelope, "content", content_attrs)
    content_builder(content)

    header = ET.SubElement(envelope, "header")
    client = ET.SubElement(header, "client")
    ET.SubElement(client, "app").text = str(app_id)
    ET.SubElement(client, "id").text = f"00{client_type}-{app_id}-{client_id}"
    ET.SubElement(client, "oem").text = oem
    ET.SubElement(client, "type").text = str(client_type)
    ET.SubElement(header, "command").text = command
    ET.SubElement(header, "flag").text = "tdkcloud"
    ET.SubElement(header, "seq").text = str(seq)
    if session_id:
        ET.SubElement(header, "session").text = session_id
    ET.SubElement(header, "user-data")
    ET.SubElement(header, "version").text = CLOUD_AUTH_VERSION

    xml = cast(
        bytes, ET.tostring(envelope, encoding="utf-8", xml_declaration=False)
    )
    return b'<?xml version="1.0" encoding="UTF-8"?>' + xml
