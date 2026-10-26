from quii_helper.streaming.rtp.g711 import G711Format
from quii_helper.streaming.rtp.h264 import DEFAULT_RTP_CLOCK_RATE


def build_h264_sdp(
    *,
    connect_host: str,
    payload_type: int,
    audio_format: G711Format | None = None,
    parameter_sets: str = "",
) -> str:
    lines = [
        "v=0",
        f"o=- 0 0 IN IP4 {connect_host}",
        "s=QUII Camera",
        "t=0 0",
        "a=control:*",
        f"m=video 0 RTP/AVP {payload_type}",
        f"a=rtpmap:{payload_type} H264/{DEFAULT_RTP_CLOCK_RATE}",
        f"a=fmtp:{payload_type} packetization-mode=1"
        + (
            f";sprop-parameter-sets={parameter_sets}" if parameter_sets else ""
        ),
        "a=control:trackID=0",
    ]
    if audio_format is not None:
        lines.extend(
            [
                f"m=audio 0 RTP/AVP {audio_format.payload_type}",
                f"a=rtpmap:{audio_format.payload_type} {audio_format.encoding}/8000/1",
                "a=control:trackID=1",
            ]
        )
    return "\r\n".join([*lines, ""])
