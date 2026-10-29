"""Small G.711 codecs for signed PCM16 LE; no audio-device dependency."""

import struct


def encode_g711(pcm: bytes, codec: int) -> bytes:
    """Encode mono PCM16 LE as native codec 4 (A-law) or 5 (mu-law).

    The caller owns sampling/pacing. Odd byte counts and other codecs are
    rejected rather than truncating samples or guessing a format.
    """
    if codec not in (4, 5):
        raise ValueError("G.711 requires codec 4 or 5")
    if len(pcm) % 2:
        raise ValueError("PCM16 LE requires an even byte count")
    result = bytearray()
    for (sample,) in struct.iter_unpack("<h", pcm):
        if codec == 4:
            mask = 0xD5 if sample >= 0 else 0x55
            value = sample if sample >= 0 else -sample - 1
            segment = max(0, value.bit_length() - 8)
            encoded = (segment << 4) | (
                (value >> (segment + 3 if segment else 4)) & 15
            )
        else:
            # Quantize signed input before taking magnitude (negative boundaries).
            sample >>= 2
            mask = 0xFF if sample >= 0 else 0x7F
            value = abs(sample) + 33
            segment = max(0, value.bit_length() - 6)
            encoded = (
                0x7F
                if segment >= 8
                else (segment << 4) | ((value >> (segment + 1)) & 15)
            )
        result.append(encoded ^ mask)
    return bytes(result)


def decode_g711(data: bytes, codec: int) -> bytes:
    """Decode native codec 4 (A-law) or 5 (mu-law) into signed PCM16 LE."""
    if codec not in (4, 5):
        raise ValueError("G.711 requires codec 4 or 5")
    result = bytearray()
    for value in data:
        if codec == 4:
            value ^= 0x55
            segment = (value >> 4) & 7
            sample = (value & 15) << 4
            sample += 8 if segment == 0 else 0x108
            if segment > 1:
                sample <<= segment - 1
            if not value & 0x80:
                sample = -sample
        else:
            value ^= 0xFF
            sample = (((value & 15) << 3) + 0x84) << ((value >> 4) & 7)
            sample = 0x84 - sample if value & 0x80 else sample - 0x84
        result.extend(struct.pack("<h", sample))
    return bytes(result)
