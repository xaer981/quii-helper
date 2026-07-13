from dataclasses import dataclass


@dataclass(frozen=True)
class CameraDeviceInfo:
    """Read-only metadata returned by the cloud for a camera device.

    Attributes:
        device_id: Device identifier used by cloud and P2P services.
        name: Device name from the cloud device list.
        memo_name: Optional user memo/alias from the cloud device list.
        channel_count: Number of channels reported by the cloud, if known.
        device_type: Vendor device type reported by userauth.
        model: Vendor model string reported by userauth.
        is_hs_device: Whether the cloud marks the device as an HS device.
        from_share: Whether access comes from a shared device grant.
        share_mode: Vendor share mode string, if present.
        password_expired: Whether the dynamic device password is expired.
        transparent_basedata: Opaque vendor metadata used by the original app
            to infer protocol capabilities.
    """

    device_id: str
    channel_count: int | None
    device_type: str
    model: str
    is_hs_device: bool | None
    from_share: bool | None
    share_mode: str
    password_expired: bool | None
    transparent_basedata: str
    name: str = ""
    memo_name: str = ""
