import hashlib

from quii_helper.device.cgi.client import (
    COMMAND_GET_STORAGE_INFO,
    request_readonly_cgi,
)
from quii_helper.device.cgi.parser import (
    parse_cgi_response,
    parse_device_all_info,
    parse_network_info,
    parse_storage_info,
)

STORAGE_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <hdd>
        <base>
          <mode>normal</mode>
          <groupmax>1</groupmax>
          <totalsum>1024</totalsum>
          <freesum>256</freesum>
          <datalist>
            <data>
              <exist>true</exist>
              <diskid>0</diskid>
              <status>normal</status>
              <name>TF Card</name>
              <attr>readwrite</attr>
              <type>local</type>
              <total>1024</total>
              <free>256</free>
              <groupid>0</groupid>
            </data>
          </datalist>
        </base>
      </hdd>
    </content>
  </body>
</envelope>
"""


NETWORK_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <network>
        <address>192.168.1.176</address>
        <submask>255.255.255.0</submask>
        <gateway>192.168.1.1</gateway>
        <idhcp>true</idhcp>
        <base>
          <lanlist>
            <lan>
              <name>eth0</name>
              <ipaddress>192.168.1.176</ipaddress>
              <subnetmask>255.255.255.0</subnetmask>
              <gateway>192.168.1.1</gateway>
              <mac>00:11:22:33:44:55</mac>
              <dhcp>false</dhcp>
            </lan>
          </lanlist>
        </base>
      </network>
    </content>
  </body>
</envelope>
"""


ALL_INFO_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <info>
        <model>IDS9483PW</model>
        <version>1.2.3</version>
        <releasedate>2026-01-02</releasedate>
        <mac>00:11:22:33:44:55</mac>
      </info>
      <wifiinfo>
        <ssid>Lab WiFi</ssid>
        <rssi>-42</rssi>
      </wifiinfo>
      <tfcard>
        <totalsum>2048</totalsum>
        <freesum>512</freesum>
      </tfcard>
      <time>
        <timezone>Europe/Moscow</timezone>
      </time>
    </content>
  </body>
</envelope>
"""


class DeviceCgiReadonlyTests:
    def test_request_readonly_cgi_uses_original_lan_auth_header(
        self, monkeypatch
    ) -> None:
        calls = []

        def fake_request_cgi(**kwargs: object) -> dict[str, str]:
            calls.append(kwargs)
            return {"raw": STORAGE_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        response = request_readonly_cgi(
            COMMAND_GET_STORAGE_INFO,
            host="192.0.2.10",
            auth_code="123456",
            port=8080,
            scheme="http",
            verify_tls=False,
        )

        assert 0 == response.error
        assert [
            {
                "command": COMMAND_GET_STORAGE_INFO,
                "host": "192.0.2.10",
                "port": 8080,
                "username": "adminapp2",
                "password": hashlib.sha256(b"123456").hexdigest(),
                "encrypted": False,
                "scheme": "http",
                "passwordencode": "1",
                "verify_tls": False,
                "debug": False,
            }
        ] == calls

    def test_parse_storage_info(self) -> None:
        info = parse_storage_info(
            parse_cgi_response(COMMAND_GET_STORAGE_INFO, STORAGE_XML)
        )

        assert 1024 == info.total_sum
        assert 256 == info.free_sum
        assert "normal" == info.mode
        assert 1 == len(info.disks)
        assert info.disks[0].exists
        assert "0" == info.disks[0].disk_id
        assert "readwrite" == info.disks[0].attributes

    def test_parse_network_info(self) -> None:
        info = parse_network_info(
            parse_cgi_response("get.network.config", NETWORK_XML)
        )

        assert "192.168.1.176" == info.address
        assert info.dhcp is True
        assert 1 == len(info.lan_interfaces)
        assert "eth0" == info.lan_interfaces[0].name
        assert info.lan_interfaces[0].dhcp is False

    def test_parse_device_all_info(self) -> None:
        info = parse_device_all_info(
            parse_cgi_response("get.device.status", ALL_INFO_XML)
        )

        assert "IDS9483PW" == info.model
        assert "1.2.3" == info.version
        assert "00:11:22:33:44:55" == info.mac
        assert "Lab WiFi" == info.ssid
        assert -42 == info.rssi
        assert 2048 == info.total_sum
        assert "Europe/Moscow" == info.time_zone
