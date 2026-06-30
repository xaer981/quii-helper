from quii_helper.streaming.rtp.h264 import DEFAULT_RTP_CLOCK_RATE


def build_h264_sdp(*, connect_host: str, payload_type: int) -> str:
    return "\r\n".join(
        [
            "v=0",
            f"o=- 0 0 IN IP4 {connect_host}",
            "s=QUII Camera",
            "t=0 0",
            "a=control:*",
            f"m=video 0 RTP/AVP {payload_type}",
            f"a=rtpmap:{payload_type} H264/{DEFAULT_RTP_CLOCK_RATE}",
            f"a=fmtp:{payload_type} packetization-mode=1",
            "a=control:trackID=0",
            "",
        ]
    )
