from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_TIMESTAMP_FORMAT = "%d-%m-%Y_%H-%M-%S"


def _resolved_data_root() -> Path:
    return DATA_DIR.resolve(strict=False)


def _is_under_data(path: Path, data_root: Path) -> bool:
    try:
        path.relative_to(data_root)
    except ValueError:
        return False
    return True


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
    data_root = ensure_data_dir()
    if directory is None:
        return data_root

    candidate = Path(directory)
    if candidate.is_absolute():
        resolved_candidate = candidate.resolve(strict=False)
        output_dir = (
            resolved_candidate
            if _is_under_data(resolved_candidate, data_root)
            else data_root / candidate.name
        )
    else:
        output_dir = data_root / _strip_data_prefix(candidate)

    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir.resolve(strict=False)


def resolve_data_path(path: str | Path) -> Path:
    data_root = ensure_data_dir()
    candidate = Path(path)
    if candidate.is_absolute():
        resolved_candidate = candidate.resolve(strict=False)
        output_path = (
            resolved_candidate
            if _is_under_data(resolved_candidate, data_root)
            else data_root / candidate.name
        )
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
    output_dir = resolve_data_dir(directory)
    stem = datetime.now().strftime(timestamp_format)
    candidate = output_dir / stem
    suffixes = (".mp4", ".jpg", ".h264")
    if not any(candidate.with_suffix(suffix).exists() for suffix in suffixes):
        return candidate.resolve()
    for index in range(2, 1000):
        candidate = output_dir / f"{stem}_{index}"
        if not any(
            candidate.with_suffix(suffix).exists() for suffix in suffixes
        ):
            return candidate.resolve()
    raise RuntimeError(
        f"could not allocate unique timestamped output name for {stem}"
    )
