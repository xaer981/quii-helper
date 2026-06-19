from dataclasses import dataclass
from urllib.parse import unquote, urlparse


@dataclass
class ParsedMqttUrl:
    scheme: str
    host: str
    port: int
    username: str | None
    password: str | None
    default_topic: str
    params: dict[str, str]

    @property
    def pubtopic(self) -> str | None:
        return self.params.get("pubtopic")

    @property
    def mqtt_username(self) -> str | None:
        return self.params.get("username") or self.username

    @property
    def mqtt_password(self) -> str | None:
        return self.params.get("password") or self.password

    @property
    def subtopic(self) -> str | None:
        return self.params.get("subtopic")

    @property
    def subtopic2(self) -> str | None:
        return self.params.get("subtopic2")

    @property
    def willtopic(self) -> str | None:
        return self.params.get("willtopic")

    @property
    def willmsg(self) -> str | None:
        return self.params.get("willmsg")

    @property
    def pubmsg(self) -> str | None:
        return self.params.get("pubmsg")

    @property
    def srcid(self) -> str | None:
        return self.params.get("srcid")

    @property
    def sver(self) -> str | None:
        return self.params.get("sVer")


def parse_mqtt_url(url: str) -> ParsedMqttUrl:
    parsed = urlparse(url)
    params: dict[str, str] = {}
    if parsed.query:
        for item in parsed.query.split("&"):
            if not item:
                continue
            key, _, value = item.partition("=")
            params[unquote(key)] = unquote(value)
    default_topic = parsed.path.lstrip("/").rstrip("/")
    return ParsedMqttUrl(
        scheme=parsed.scheme,
        host=parsed.hostname or "",
        port=parsed.port or 0,
        username=parsed.username,
        password=parsed.password,
        default_topic=default_topic,
        params=params,
    )
