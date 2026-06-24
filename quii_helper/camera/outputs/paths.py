from pathlib import Path


def validate_output_path(
    output_path: str | Path | None, expected_suffix: str
) -> Path | None:
    if output_path is None:
        return None
    path = Path(output_path)
    if path.suffix and path.suffix.lower() != expected_suffix:
        raise ValueError(f"output_path must use {expected_suffix} suffix")
    return path


def output_base_from_path(output_path: str | Path | None) -> Path | None:
    if output_path is None:
        return None
    path = Path(output_path)
    return path.with_suffix("") if path.suffix else path
