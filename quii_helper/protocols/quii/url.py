DEFAULT_QUII_CHANNEL = 1
DEFAULT_QUII_STREAM = 2
DEFAULT_QUII_AP = 2


def build_quii_live_path(
    channel: int | None = None,
    stream: int | None = None,
    ap: int = DEFAULT_QUII_AP,
    inner: bool = False,
    newcn: bool = False,
    connect_mode: int | None = None,
) -> str:
    channel = DEFAULT_QUII_CHANNEL if channel is None else channel
    stream = DEFAULT_QUII_STREAM if stream is None else stream
    path = f"/mode=real&idc={channel}&ids={stream}"
    if inner:
        path += "&inner=1"
    if newcn:
        path += "&newcn=1"
    if connect_mode is not None:
        path += f"&connect_mode={int(connect_mode)}"
    path += f"&ap={ap}"
    return path


def quii_escape_password(value: str) -> str:
    return value.replace("@", "@@") if value else ""


def build_quii_live_url(
    username: str,
    password: str,
    host: str,
    port: int,
    *,
    channel: int | None = None,
    stream: int | None = None,
    ap: int = DEFAULT_QUII_AP,
    inner: bool = False,
    newcn: bool = False,
    connect_mode: int | None = None,
) -> str:
    path = build_quii_live_path(
        channel=channel,
        stream=stream,
        ap=ap,
        inner=inner,
        newcn=newcn,
        connect_mode=connect_mode,
    )
    return (
        f"quii://{username}:{quii_escape_password(password)}"
        f"@{host}:{port}{path}"
    )
