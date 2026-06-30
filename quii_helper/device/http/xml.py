import xml.etree.ElementTree as ET
from typing import cast


def build_request_xml(
    command: str,
    security: str,
    username: str,
    password: str,
    nc: str | None = None,
    passwordencode: str | None = None,
) -> bytes:
    envelope = ET.Element("envelope")

    body = ET.SubElement(envelope, "body")
    ET.SubElement(body, "command").text = command
    ET.SubElement(body, "content")

    header = ET.SubElement(envelope, "header")
    ET.SubElement(header, "password").text = password
    if passwordencode is not None:
        ET.SubElement(header, "passwordencode").text = passwordencode
    ET.SubElement(header, "security").text = security
    ET.SubElement(header, "username").text = username
    if nc:
        ET.SubElement(header, "nc").text = nc

    return cast(
        bytes, ET.tostring(envelope, encoding="utf-8", xml_declaration=False)
    )
