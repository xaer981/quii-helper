from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CameraDeviceShadowSwitchState:
    """Switch state reported by the cloud device shadow API.

    Attributes:
        channel: Native switch channel number.
        index: Native switch index.
        state: Native switch state value.
        type: Native switch type value.
        raw: Raw JSON object for vendor-specific fields.
    """

    channel: int | None
    index: int | None
    state: int | None
    type: int | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class CameraDeviceShadowState:
    """Device state block reported by the cloud device shadow API.

    Attributes:
        f1_state: Native `F1_state` value.
        switch_state: Optional nested switch state.
        private_mode_state: Native `Private_mode_state` value.
        raw: Raw JSON object for vendor-specific fields.
    """

    f1_state: int | None
    switch_state: CameraDeviceShadowSwitchState | None
    private_mode_state: int | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class CameraDeviceShadowInfo:
    """Read-only cloud shadow status for a camera.

    Attributes:
        code: Cloud shadow response code.
        thing_id: Device UID/UMID returned by the shadow service.
        device_state: Parsed `Device_state` block when present.
        fields: Raw `fields` object returned by the cloud.
        message: Response message.
        error_tip: Response error tip.
        path: Response path.
        timestamp: Response timestamp.
        raw: Full raw JSON response.
    """

    code: int
    thing_id: str
    device_state: CameraDeviceShadowState | None
    fields: dict[str, Any]
    message: str
    error_tip: str
    path: str
    timestamp: int | None
    raw: dict[str, Any]
