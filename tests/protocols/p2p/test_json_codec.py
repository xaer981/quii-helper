import json
import unittest

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


class P2PJsonCodecTests(unittest.TestCase):
    def test_maybe_int_preserves_current_conversions(self) -> None:
        self.assertIsNone(maybe_int(None))
        self.assertIsNone(maybe_int(" "))
        self.assertEqual(1, maybe_int(True))
        self.assertEqual(7, maybe_int(7.8))
        self.assertEqual(42, maybe_int("42"))

        with self.assertRaises(TypeError):
            maybe_int(object())

    def test_json_state_helpers_decode_content_and_lists(self) -> None:
        payload = {"content": {"value": 1}}

        self.assertEqual(payload, decoded_json_object(json.dumps(payload)))
        self.assertEqual({"value": 1}, content_or_self(payload))
        self.assertEqual(["a", "2"], list_of_strings(["a", 2]))
        self.assertEqual(["single"], list_of_strings("single"))
        self.assertEqual([], list_of_strings(None))
        self.assertEqual(["None"], list_of_strings([None]))
        self.assertEqual([], list_of_strings([None], omit_none_items=True))

    def test_parse_kcp_params_normalizes_native_nomal_typo(self) -> None:
        params = parse_kcp_params({"mode": "nomal", "mtu": "1200"})

        self.assertEqual("normal", params.mode)
        self.assertEqual(1200, params.mtu)

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

        self.assertEqual("0", response.result_code)
        self.assertEqual("ok", response.result_message)
        self.assertEqual("device", response.device_id)
        self.assertEqual("flag", response.session_flag)
        self.assertEqual(123, response.response_session_id)
        self.assertEqual(1, response.nettype)
        self.assertEqual(2, response.netsubtype)
        self.assertEqual("203.0.113.1", response.public_ip)
        self.assertEqual(1000, response.public_udp_port)
        self.assertEqual(2000, response.local_udp_port)
        self.assertEqual(["192.168.1.2"], response.local_ips)
        self.assertEqual("198.51.100.1", response.utd_public_ip)
        self.assertEqual(3000, response.utd_public_udp_port)
        self.assertEqual("normal", response.kcp_params.mode)
        self.assertEqual(4, response.kcp_params.sndwnd)

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

        self.assertEqual(["device"], parsed.device_ids)
        self.assertEqual(["a", "2"], parsed.registered)
        self.assertEqual(["b"], parsed.unregistered)
        self.assertEqual(["a"], parsed.online)
        self.assertEqual(["b"], parsed.offline)
        self.assertEqual("key-1", parsed.usrkey)

    def test_result_code_and_message_helpers_keep_existing_shape(self) -> None:
        self.assertEqual("0", result_code_value({"code": 0}))
        self.assertIsNone(result_code_value({}))
        self.assertEqual("msg", result_message_value({"msg": "msg"}))
        self.assertEqual(
            "message",
            result_message_value({"message": "message"}),
        )


if __name__ == "__main__":
    unittest.main()
