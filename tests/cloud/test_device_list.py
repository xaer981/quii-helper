import xml.etree.ElementTree as ET

from quii_helper.cloud.devices.requests import build_device_list_xml
from quii_helper.cloud.devices.responses import parse_device_list_response
from quii_helper.config import AutonomousConfig


def _config() -> AutonomousConfig:
    return AutonomousConfig(
        device_id="device-id",
        cloud_account="account",
        cloud_password="password",
        service_url="https://service.example",
        auth_url="https://auth.example",
        oem="OEM",
        app_id=1,
        client_type=2,
        client_id="client-id",
        ip_region_id=3,
    )


class CloudDeviceListTests:
    def test_build_device_list_xml_matches_native_command_shape(self) -> None:
        root = ET.fromstring(
            build_device_list_xml(
                _config(),
                session_id="session-1",
                count=50,
                page=2,
            )
        )

        assert "get-device-list" == root.findtext("./header/command")
        assert "session-1" == root.findtext("./header/session")
        assert "50" == root.findtext("./content/count")
        assert "2" == root.findtext("./content/page")
        assert "0" == root.findtext("./content/order")
        assert "" == (root.findtext("./content/filter") or "")
        assert "" == (root.findtext("./content/owner") or "")

    def test_parse_device_list_response_reads_device_metadata(self) -> None:
        root = ET.fromstring("""
            <envelope>
              <header><result>0</result></header>
              <content>
                <count>1</count>
                <device>
                  <id>22058iwsv6av</id>
                  <name>Front Door</name>
                  <memo-name>Main entrance</memo-name>
                  <channel-num>2</channel-num>
                  <type>doorphone</type>
                  <model>Tantos Marilyn Wi-Fi s</model>
                  <is-hs-device>0</is-hs-device>
                  <from-share>0</from-share>
                  <share-mode>owner</share-mode>
                  <password-expired>false</password-expired>
                  <transparent-basedata>ASBHDz8=</transparent-basedata>
                </device>
              </content>
            </envelope>
            """)

        devices, total_count = parse_device_list_response(root)

        assert 1 == total_count
        assert 1 == len(devices)
        device = devices[0]
        assert "22058iwsv6av" == device.device_id
        assert "Front Door" == device.name
        assert "Main entrance" == device.memo_name
        assert 2 == device.channel_count
        assert "doorphone" == device.device_type
        assert "Tantos Marilyn Wi-Fi s" == device.model
        assert device.is_hs_device is False
        assert device.from_share is False
        assert "owner" == device.share_mode
        assert device.password_expired is False
        assert "ASBHDz8=" == device.transparent_basedata
