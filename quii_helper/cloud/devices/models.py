from dataclasses import dataclass


@dataclass(frozen=True)
class CloudDeviceListEntry:
    """Single camera entry returned by cloud `get-device-list`."""

    device_id: str
    name: str
    memo_name: str
    channel_count: int | None
    device_type: str
    model: str
    is_hs_device: bool | None
    from_share: bool | None
    share_mode: str
    password_expired: bool | None
    transparent_basedata: str
