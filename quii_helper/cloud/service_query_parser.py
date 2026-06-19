import xml.etree.ElementTree as ET

from quii_helper.config import ServiceEntry, ServiceQueryResponse


def parse_service_query_response(xml_text: str) -> ServiceQueryResponse:
    root = ET.fromstring(xml_text)
    header = root.find("header")
    content = root.find("content")
    if header is None or content is None:
        raise RuntimeError(
            f"unexpected query-hlrv2 response: {xml_text[:400]}"
        )

    return ServiceQueryResponse(
        seq=int(header.findtext("seq") or "0"),
        timestamp=int(header.findtext("timestamp") or "0"),
        result=int(header.findtext("result") or "-1"),
        client_region_id=int(content.findtext("client-regionid") or "0"),
        re_maxtime=int(content.findtext("re-maxtime") or "0"),
        ip_validity=int(content.findtext("ip-validity") or "0"),
        servers=_parse_service_entries(content),
    )


def _parse_service_entries(content: ET.Element) -> list[ServiceEntry]:
    return [
        ServiceEntry(
            server_type=(server.findtext("server-type") or "").strip(),
            query_result=int(server.findtext("query-result") or "0"),
            region_id=int(server.findtext("regionid") or "0"),
            url=(server.findtext("url") or "").strip(),
            uri=(server.findtext("uri") or "").strip(),
            param=(server.findtext("param") or "").strip(),
        )
        for server in content.findall("server")
    ]
