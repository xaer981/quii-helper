import json

from quii_helper.protocols.p2p import request_models, response_models
from quii_helper.protocols.p2p.models import (
    KcpParams,
    P2PConnectRequest,
    P2PConnectResponse,
    ParsedP2PTestResponse,
    ParsedP2PTransportFrame,
)


class P2PModelTests:
    def test_kcp_params_preserves_native_dict_shape(self) -> None:
        assert {"mode": "normal"} == KcpParams().to_dict()
        assert {"mode": "normal", "mtu": 1200} == (
            KcpParams(mtu=1200).to_dict()
        )
        assert {
            "mode": "custom",
            "sndwnd": 1,
            "rcvwnd": 2,
            "mtu": 1300,
        } == (
            KcpParams(
                mode="custom",
                sndwnd=1,
                rcvwnd=2,
                mtu=1300,
            ).to_dict()
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

        assert data == parsed_json
        assert "tdkcloud" == data["header"]["flag"]
        assert "p2pconnect" == data["header"]["command"]
        assert "1" == data["header"]["client"]["type"]
        assert "7" == data["header"]["client"]["app"]
        assert 9 == data["header"]["seq"]
        assert "session-1" == data["header"]["session"]
        assert "user-data" == data["header"]["userdata"]
        assert "device-1" == data["content"]["devid"]
        assert "flag-1" == data["content"]["session-flag"]
        assert 123 == data["content"]["requ-session-id"]
        assert 1 == data["content"]["force-trans"]
        assert {"mode": "normal", "mtu": 1200} == (data["content"]["kcpParam"])
        assert {"monChn": 2} == data["content"]["devTrans"]
        assert "ipc" == data["content"]["devType"]
        assert "sub" == data["content"]["devSubState"]

    def test_response_properties_keep_truthy_port_behavior(self) -> None:
        response = P2PConnectResponse(
            public_ip="203.0.113.1",
            public_udp_port=0,
            utd_public_ip="198.51.100.1",
            utd_public_udp_port=1000,
        )

        assert not response.supports_p2p_test
        assert response.supports_trans_test

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

        assert ok.ok
        assert request_frame.is_request
        assert not request_frame.is_response

    def test_models_module_keeps_compatibility_class_identities(self) -> None:
        assert request_models.KcpParams is KcpParams
        assert request_models.P2PConnectRequest is P2PConnectRequest
        assert response_models.P2PConnectResponse is P2PConnectResponse
        assert response_models.ParsedP2PTestResponse is (ParsedP2PTestResponse)
