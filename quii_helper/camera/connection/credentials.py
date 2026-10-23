"""Explicit persistence of the minimal credentials for direct LAN playback."""

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from quii_helper.device.security.streamkey import validate_stream_credentials
from quii_helper.support.errors import ConfigurationError

MAX_CREDENTIAL_FILE_BYTES = 4096


@dataclass(frozen=True)
class CameraStreamCredentials:
    """Device-bound LAN playback secrets, separate from a cloud login session.

    Attributes:
        device_id: Device id associated with this key/auth pair.
        stream_key: Saved 32-byte UTF-8 key, hidden from representations.
        auth_code: Matching raw or encoded auth code, also hidden from repr.

    Construction validates values but performs no I/O. Expiry is unknown;
    neither loading nor LAN playback renews these credentials automatically.
    """

    device_id: str
    stream_key: str = field(repr=False)
    auth_code: str = field(repr=False)

    def __post_init__(self) -> None:
        """Validate the device identity and key/auth pair without I/O."""
        if not isinstance(self.device_id, str) or not self.device_id.strip():
            raise ConfigurationError("stream credentials require a device_id")
        validate_stream_credentials(self.stream_key, self.auth_code)

    def save(self, path: str | Path) -> Path:
        """Atomically save minimal plaintext JSON, replacing an existing file.

        Args:
            path: Application-owned destination; prefer an ignored private
                directory such as `data/`. Relative paths use the current cwd.

        Returns:
            Absolute path to the saved file. Parent directories are created.

        Raises:
            ConfigurationError: Serialized credentials exceed the file limit.
            OSError: Writing or replacing the destination failed. The previous
                file is preserved if publication fails.

        The temporary file has owner-only permissions on Unix; Windows uses
        the directory's ACL. This is not encryption or an OS credential vault.
        Cloud passwords, sessions and raw responses are never serialized.
        """
        data = (
            json.dumps(
                {
                    "version": 1,
                    "device_id": self.device_id,
                    "stream_key": self.stream_key,
                    "auth_code": self.auth_code,
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n"
        )
        if len(data.encode("utf-8")) > MAX_CREDENTIAL_FILE_BYTES:
            raise ConfigurationError(
                "stream credentials exceed file size limit"
            )
        target = Path(path).expanduser().absolute()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                delete=False,
                dir=target.parent,
                prefix=f".{target.name}.",
            ) as output:
                temporary = Path(output.name)
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return target

    @classmethod
    def load(cls, path: str | Path) -> "CameraStreamCredentials":
        """Read and validate a saved key/auth pair without network access.

        Args:
            path: JSON file previously written by `save()`.

        Returns:
            Validated LAN credentials; secrets are not printed or logged.

        Raises:
            ConfigurationError: File is oversized, malformed, has an unknown
                schema, or contains invalid credentials.
            OSError: The file is missing or cannot be read.
        """
        with Path(path).expanduser().open("rb") as source:
            data = source.read(MAX_CREDENTIAL_FILE_BYTES + 1)
        if len(data) > MAX_CREDENTIAL_FILE_BYTES:
            raise ConfigurationError(
                "stream credentials exceed file size limit"
            )
        try:
            values = json.loads(data.decode("utf-8"))
        except (UnicodeError, ValueError, RecursionError):
            raise ConfigurationError(
                "invalid stream credentials JSON"
            ) from None
        if (
            not isinstance(values, dict)
            or set(values)
            != {"version", "device_id", "stream_key", "auth_code"}
            or type(values["version"]) is not int
            or values["version"] != 1
        ):
            raise ConfigurationError("unsupported stream credentials schema")
        return cls(
            device_id=values["device_id"],
            stream_key=values["stream_key"],
            auth_code=values["auth_code"],
        )
