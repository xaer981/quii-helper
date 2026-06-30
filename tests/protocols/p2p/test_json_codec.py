import json

import pytest

from quii_helper.protocols.p2p.codec.json_codec import (
    maybe_int,
    parse_p2pconnect_response,
    parse_sub_device_state_response,
)
from quii_helper.protocols.p2p.codec.json_state import (
    content_or_self,
    decoded_json_object,
    list_of_strings,
    parse_kcp_params,
    result_code_value,
    result_message_value,
)


class P2PJsonCodecTests:
    def test_maybe_int_preserves_current_conversions(self) -> None:
        assert maybe_int(None) is None
        assert maybe_int(" ") is None
        assert 1 == maybe_int(True)
        assert 7 == maybe_int(7.8)
        assert 42 == maybe_int("42")

        with pytest.raises(TypeError):
            maybe_int(object())

    def test_json_state_helpers_decode_content_and_lists(self) -> None:
        payload = {"content": {"value": 1}}

        assert payload == decoded_json_object(json.dumps(payload))
        assert {"value": 1} == content_or_self(payload)
        assert ["a", "2"] == list_of_strings(["a", 2])
        assert ["single"] == list_of_strings("single")
        assert [] == list_of_strings(None)
        assert ["None"] == list_of_strings([None])
        assert [] == list_of_strings([None], omit_none_items=True)

    def test_parse_kcp_params_normalizes_native_nomal_typo(self) -> None:
        params = parse_kcp_params({"mode": "nomal", "mtu": "1200"})

        assert "normal" == params.mode
        assert 1200 == params.mtu

    def test_parse_p2pconnect_response_accepts_nested_content(self) -> None:
        response = parse_p2pconnect_response(
            {
                "content": {
                    "result": {"code": 0, "msg": "ok"},
                    "devid": "device",
                    "session-flag": "flag",
                    "resp-session-id": "123",
                    "nettype": "1",
                    "netsubtype": "2",
                    "pub-ip": "203.0.113.1",
                    "pub-udpport": "1000",
                    "loc-udpport": "2000",
                    "loc-ip": "192.168.1.2",
                    "utd-pub-ip": "198.51.100.1",
                    "utd-pub-udpport": "3000",
                    "kcpParam": {"mode": "nomal", "sndwnd": "4"},
                }
            }
        )

        assert "0" == response.result_code
        assert "ok" == response.result_message
        assert "device" == response.device_id
        assert "flag" == response.session_flag
        assert 123 == response.response_session_id
        assert 1 == response.nettype
        assert 2 == response.netsubtype
        assert "203.0.113.1" == response.public_ip
        assert 1000 == response.public_udp_port
        assert 2000 == response.local_udp_port
        assert ["192.168.1.2"] == response.local_ips
        assert "198.51.100.1" == response.utd_public_ip
        assert 3000 == response.utd_public_udp_port
        assert "normal" == response.kcp_params.mode
        assert 4 == response.kcp_params.sndwnd

    def test_parse_sub_device_state_response_normalizes_lists(self) -> None:
        parsed = parse_sub_device_state_response(
            {
                "content": {
                    "devices": "device",
                    "state-r": {
                        "register": ["a", 2],
                        "unregister": "b",
                        "usrkey": ["key-1", "key-2"],
                    },
                    "state-s": {"aonline": "a", "aoffline": ["b"]},
                }
            }
        )

        assert ["device"] == parsed.device_ids
        assert ["a", "2"] == parsed.registered
        assert ["b"] == parsed.unregistered
        assert ["a"] == parsed.online
        assert ["b"] == parsed.offline
        assert "key-1" == parsed.usrkey

    def test_result_code_and_message_helpers_keep_existing_shape(self) -> None:
        assert "0" == result_code_value({"code": 0})
        assert result_code_value({}) is None
        assert "msg" == result_message_value({"msg": "msg"})
        assert "message" == (result_message_value({"message": "message"}))
