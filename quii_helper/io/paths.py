from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(".")
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_TIMESTAMP_FORMAT = "%d-%m-%Y_%H-%M-%S"


def _resolved_data_root() -> Path:
    return DATA_DIR.resolve(strict=False)


def _strip_data_prefix(path: Path) -> Path:
    parts = path.parts
    if parts and parts[0].lower() == DATA_DIR.name.lower():
        return Path(*parts[1:]) if len(parts) > 1 else Path()
    return path


def ensure_data_dir() -> Path:
    data_root = _resolved_data_root()
    data_root.mkdir(parents=True, exist_ok=True)
    return data_root


def resolve_data_dir(directory: str | Path | None = None) -> Path:
    """Create an output directory, honoring absolute application paths."""
    data_root = _resolved_data_root()
    if directory is None:
        output_dir = data_root
    else:
        candidate = Path(directory).expanduser()
        output_dir = (
            candidate
            if candidate.is_absolute()
            else data_root / _strip_data_prefix(candidate)
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir.resolve(strict=False)


def resolve_data_path(path: str | Path) -> Path:
    """Create parent directories without remapping absolute output paths."""
    data_root = _resolved_data_root()
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        output_path = candidate
    else:
        output_path = data_root / _strip_data_prefix(candidate)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path.resolve(strict=False)


def data_path(*parts: str | Path) -> Path:
    return resolve_data_path(Path(*parts))


def timestamped_output_base(
    directory: Path | None = None,
    *,
    timestamp_format: str = OUTPUT_TIMESTAMP_FORMAT,
) -> Path:
    """Reserve a timestamped name with an exclusive, empty H.264 placeholder.

    The output writer removes an unused placeholder when it finishes.
    """
    output_dir = resolve_data_dir(directory)
    stem = datetime.now().strftime(timestamp_format)
    suffixes = (".mp4", ".jpg", ".h264")
    for index in range(1, 1000):
        candidate = output_dir / (stem if index == 1 else f"{stem}_{index}")
        if any(
            candidate.with_name(candidate.name + suffix).exists()
            for suffix in suffixes
        ):
            continue
        reservation = candidate.with_name(candidate.name + ".h264")
        try:
            with reservation.open("xb"):
                pass
        except FileExistsError:
            continue
        # A previous writer may have published its outputs after our first check.
        if any(
            candidate.with_name(candidate.name + suffix).exists()
            for suffix in suffixes[:2]
        ):
            reservation.unlink()
            continue
        return candidate.resolve()
    raise RuntimeError(
        f"could not allocate unique timestamped output name for {stem}"
    )
