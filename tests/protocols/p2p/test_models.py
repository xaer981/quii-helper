import json
import unittest

from quii_helper.protocols.p2p import request_models, response_models
from quii_helper.protocols.p2p.models import (
    KcpParams,
    P2PConnectRequest,
    P2PConnectResponse,
    ParsedP2PTestResponse,
    ParsedP2PTransportFrame,
)


class P2PModelTests(unittest.TestCase):
    def test_kcp_params_preserves_native_dict_shape(self) -> None:
        self.assertEqual({"mode": "normal"}, KcpParams().to_dict())
        self.assertEqual(
            {"mode": "normal", "mtu": 1200},
            KcpParams(mtu=1200).to_dict(),
        )
        self.assertEqual(
            {
                "mode": "custom",
                "sndwnd": 1,
                "rcvwnd": 2,
                "mtu": 1300,
            },
            KcpParams(
                mode="custom",
                sndwnd=1,
                rcvwnd=2,
                mtu=1300,
            ).to_dict(),
        )

    def test_p2p_connect_request_serializes_optional_fields(self) -> None:
        request = P2PConnectRequest(
            client_id="client-1",
            client_type=1,
            oem="OEM",
            app=7,
            device_id="device-1",
            session_flag="flag-1",
            request_session_id=123,
            mon_channel=2,
            force_trans=1,
            dev_type="ipc",
            dev_sub_state="sub",
            seq=9,
            session="session-1",
            userdata="user-data",
            kcp_params=KcpParams(mtu=1200),
        )

        data = request.to_dict()
        parsed_json = json.loads(request.to_json())

        self.assertEqual(data, parsed_json)
        self.assertEqual("tdkcloud", data["header"]["flag"])
        self.assertEqual("p2pconnect", data["header"]["command"])
        self.assertEqual("1", data["header"]["client"]["type"])
        self.assertEqual("7", data["header"]["client"]["app"])
        self.assertEqual(9, data["header"]["seq"])
        self.assertEqual("session-1", data["header"]["session"])
        self.assertEqual("user-data", data["header"]["userdata"])
        self.assertEqual("device-1", data["content"]["devid"])
        self.assertEqual("flag-1", data["content"]["session-flag"])
        self.assertEqual(123, data["content"]["requ-session-id"])
        self.assertEqual(1, data["content"]["force-trans"])
        self.assertEqual(
            {"mode": "normal", "mtu": 1200},
            data["content"]["kcpParam"],
        )
        self.assertEqual({"monChn": 2}, data["content"]["devTrans"])
        self.assertEqual("ipc", data["content"]["devType"])
        self.assertEqual("sub", data["content"]["devSubState"])

    def test_response_properties_keep_truthy_port_behavior(self) -> None:
        response = P2PConnectResponse(
            public_ip="203.0.113.1",
            public_udp_port=0,
            utd_public_ip="198.51.100.1",
            utd_public_udp_port=1000,
        )

        self.assertFalse(response.supports_p2p_test)
        self.assertTrue(response.supports_trans_test)

    def test_small_response_flags_keep_existing_semantics(self) -> None:
        ok = ParsedP2PTestResponse(
            result_code=0,
            session_flag="flag",
            address="127.0.0.1",
            port=1,
            status_code=0,
            test_id=2,
        )
        request_frame = ParsedP2PTransportFrame(
            marker=0,
            packet_type_flag=0,
            command=1,
            seq=2,
            session_flag="flag",
            remote_ip="",
            remote_port=0,
            tail_code=102,
        )

        self.assertTrue(ok.ok)
        self.assertTrue(request_frame.is_request)
        self.assertFalse(request_frame.is_response)

    def test_models_module_keeps_compatibility_class_identities(self) -> None:
        self.assertIs(request_models.KcpParams, KcpParams)
        self.assertIs(request_models.P2PConnectRequest, P2PConnectRequest)
        self.assertIs(response_models.P2PConnectResponse, P2PConnectResponse)
        self.assertIs(
            response_models.ParsedP2PTestResponse,
            ParsedP2PTestResponse,
        )


if __name__ == "__main__":
    unittest.main()
