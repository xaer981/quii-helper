def build_live_credentials_body(
    username: str, password: str, target: str
) -> bytes:
    return (
        username.encode("utf-8")
        + b"&&"
        + password.encode("utf-8")
        + b"\x00"
        + target.encode("utf-8")
        + b"\x00"
    )


def build_live_path_body(username: str, password: str, path: str) -> bytes:
    return build_live_credentials_body(username, password, path)


def build_live_oem_body(username: str, password: str, oem: str) -> bytes:
    return build_live_credentials_body(username, password, oem)
