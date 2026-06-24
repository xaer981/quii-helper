import unittest

from quii_helper.cloud.services.discovery_state import (
    cloud_login_kwargs,
    device_token_kwargs,
    runtime_credentials_from_cloud_results,
    service_query_request_parts,
)
from quii_helper.config import AutonomousConfig


class CloudServiceDiscoveryStateTests(unittest.TestCase):
    def test_service_query_request_parts_preserve_url_host_and_xml(
        self,
    ) -> None:
        config = AutonomousConfig(
            service_url="https://service.example/base/",
            oem="OEM",
            client_id="client-1",
            ip_region_id=7,
        )

        request_url, xml_body, host = service_query_request_parts(
            config,
            seq=9,
            server_types=("p2papp", "natcheck"),
        )

        self.assertEqual(
            "https://service.example/base/mst/query",
            request_url,
        )
        self.assertEqual("service.example", host)
        xml = xml_body.decode("utf-8")
        self.assertIn("<seq>9</seq>", xml)
        self.assertIn("<server-type>p2papp,natcheck</server-type>", xml)
        self.assertIn("<oem>OEM</oem>", xml)
        self.assertIn("<client-id>client-1</client-id>", xml)
        self.assertIn("<regionid>7</regionid>", xml)

    def test_cloud_request_kwargs_preserve_existing_fields(self) -> None:
        config = AutonomousConfig(
            auth_url="https://auth.example",
            client_id="client-1",
            oem="OEM",
            app_id=12,
            client_type=34,
            ip_region_id=56,
        )

        self.assertEqual(
            {
                "auth_url": "https://auth.example",
                "ip_region_id": 56,
                "client_id": "client-1",
                "oem": "OEM",
                "app_id": 12,
                "client_type": 34,
                "debug": False,
            },
            cloud_login_kwargs(config),
        )
        self.assertEqual(
            {
                "auth_url": "https://auth.example",
                "client_id": "client-1",
                "oem": "OEM",
                "app_id": 12,
                "client_type": 34,
                "debug": False,
            },
            device_token_kwargs(config),
        )

    def test_runtime_credentials_from_cloud_results_preserves_raw_payloads(
        self,
    ) -> None:
        login = {"session_id": "session-1"}
        token = {
            "dynamic_password": "dyn",
            "data_encode_key": "key",
            "auth_code": "auth",
            "transparent_basedata": "base",
        }

        credentials = runtime_credentials_from_cloud_results(
            login=login,
            token=token,
        )

        self.assertEqual("session-1", credentials.session_id)
        self.assertEqual("dyn", credentials.dynamic_password)
        self.assertEqual("key", credentials.data_encode_key)
        self.assertEqual("auth", credentials.auth_code)
        self.assertEqual("base", credentials.transparent_basedata)
        self.assertEqual({"login": login, "token": token}, credentials.raw)


if __name__ == "__main__":
    unittest.main()
