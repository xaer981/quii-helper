def capture_settings_overrides(
    *,
    duration_seconds: float | None,
    save_diagnostic_artifacts: bool | None,
    stop_when_decodable: bool | None,
) -> dict[str, object]:
    values: dict[str, object] = {}
    if duration_seconds is not None:
        values["capture_seconds"] = normalized_duration_seconds(
            duration_seconds
        )
    if save_diagnostic_artifacts is not None:
        values["save_diagnostic_artifacts"] = bool(save_diagnostic_artifacts)
    if stop_when_decodable is not None:
        values["stop_when_decodable"] = bool(stop_when_decodable)
    return values


def normalized_duration_seconds(duration_seconds: float) -> float:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be greater than zero")
    return float(duration_seconds)
