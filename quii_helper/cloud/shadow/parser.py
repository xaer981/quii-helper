from collections.abc import Mapping
from typing import Any

from quii_helper.cloud.shadow.models import (
    CameraDeviceShadowInfo,
    CameraDeviceShadowState,
    CameraDeviceShadowSwitchState,
)
from quii_helper.support.errors import QuiiConnectionError


def parse_device_shadow_info(
    payload: Mapping[str, Any],
) -> CameraDeviceShadowInfo:
    """Parse native-compatible cloud shadow JSON response."""

    raw = dict(payload)
    data = _mapping(raw.get("data"))
    fields = _mapping(data.get("fields"))
    device_state_raw = _mapping(
        _first_present(fields, "Device_state", "device_state")
    )

    device_state = (
        _parse_device_state(device_state_raw) if device_state_raw else None
    )
    return CameraDeviceShadowInfo(
        code=_int(raw.get("code"), default=-1),
        thing_id=str(data.get("thingId") or data.get("thing_id") or ""),
        device_state=device_state,
        fields=dict(fields),
        message=str(raw.get("msg") or raw.get("message") or ""),
        error_tip=str(raw.get("errTip") or raw.get("error_tip") or ""),
        path=str(raw.get("path") or ""),
        timestamp=_optional_int(raw.get("timestamp")),
        raw=raw,
    )


def _parse_device_state(
    raw: Mapping[str, Any],
) -> CameraDeviceShadowState:
    switch_state_raw = _mapping(
        _first_present(raw, "Switch_state", "switch_state")
    )
    switch_state = (
        _parse_switch_state(switch_state_raw) if switch_state_raw else None
    )
    return CameraDeviceShadowState(
        f1_state=_optional_int(_first_present(raw, "F1_state", "f1_state")),
        switch_state=switch_state,
        private_mode_state=_optional_int(
            _first_present(raw, "Private_mode_state", "private_mode_state")
        ),
        raw=dict(raw),
    )


def _parse_switch_state(
    raw: Mapping[str, Any],
) -> CameraDeviceShadowSwitchState:
    return CameraDeviceShadowSwitchState(
        channel=_optional_int(raw.get("channel")),
        index=_optional_int(raw.get("index")),
        state=_optional_int(raw.get("state")),
        type=_optional_int(raw.get("type")),
        raw=dict(raw),
    )


def _first_present(mapping: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return _int(value, default=None)


def _int(value: Any, *, default: int | None) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        if default is not None:
            return default
        raise QuiiConnectionError(
            f"unexpected shadow integer value: {value!r}"
        ) from exc
