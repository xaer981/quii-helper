from dataclasses import dataclass
from typing import cast

from quii_helper.models.packets import DecodedQuiiMessage
from quii_helper.protocols.quii.blob import decode_quii_blob


@dataclass(frozen=True)
class MediaPacketDecoder:
    """Decode raw QUII blobs into typed message payloads."""

    key: str
    crypto_mode: int = 2

    def decode(self, blob: bytes) -> DecodedQuiiMessage:
        return cast(
            DecodedQuiiMessage,
            decode_quii_blob(blob, self.key, crypto_mode=self.crypto_mode),
        )
