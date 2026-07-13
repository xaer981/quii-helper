import hashlib
import xml.etree.ElementTree as ET

from quii_helper.device.cgi.client import (
    COMMAND_GET_STORAGE_INFO,
    request_readonly_cgi,
)
from quii_helper.device.cgi.parser import (
    parse_cgi_response,
    parse_device_all_info,
    parse_network_info,
    parse_product_info,
    parse_screen_flip_info,
    parse_storage_info,
    parse_system_capabilities,
    parse_system_general_info,
    parse_time_info,
    parse_time_title_info,
    parse_video_config_info,
    parse_video_switch_info,
    parse_wifi_list_info,
)
from quii_helper.device.http.xml import build_request_xml

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


PRODUCT_INFO_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <info>
        <mac>00:11:22:33:44:55</mac>
        <version>1.2.3</version>
        <releasedate>2026-01-02</releasedate>
        <model>IDS9483PW</model>
      </info>
    </content>
  </body>
</envelope>
"""


TIME_INFO_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <time>
        <timezone>Europe/Moscow</timezone>
        <datetime>2026-06-24 15:31:00</datetime>
      </time>
    </content>
  </body>
</envelope>
"""


WIFI_LIST_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <wifilist>
        <wifi>
          <id>0</id>
          <ssid>Lab WiFi</ssid>
          <rssi>-42</rssi>
          <encry>0</encry>
        </wifi>
        <wifi>
          <id>1</id>
          <ssid></ssid>
          <rssi>-80</rssi>
          <encry>1</encry>
        </wifi>
        <wifi>
          <id>2</id>
          <ssid>Open WiFi</ssid>
          <rssi>-65</rssi>
          <encry>1</encry>
        </wifi>
      </wifilist>
    </content>
  </body>
</envelope>
"""


SCREEN_FLIP_XML = """
<envelop>
  <body>
    <error>0</error>
    <content>
      <mirror>
        <value>up_down</value>
      </mirror>
      <rotate>
        <value>r180</value>
      </rotate>
    </content>
  </body>
</envelop>
"""


VIDEO_SWITCH_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <vionoff>
        <value>video_on</value>
      </vionoff>
    </content>
  </body>
</envelope>
"""


TIME_TITLE_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <datalist>
        <data>
          <streamtype>1</streamtype>
          <videowidth>960</videowidth>
          <videoheight>576</videoheight>
          <titlewidth>260</titlewidth>
          <titleheight>32</titleheight>
          <x>20</x>
          <y>30</y>
        </data>
      </datalist>
    </content>
  </body>
</envelope>
"""


SYSTEM_GENERAL_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <system>
        <general>
          <language>
            <value>ru</value>
            <supported>en;ru</supported>
          </language>
          <autosynctime>true</autosynctime>
          <timezone>Europe/Moscow</timezone>
          <datetime>2026-06-24 15:31:00</datetime>
          <deviceid>22058iwsv6av</deviceid>
          <hostname>
            <value>front-door</value>
            <supported>true</supported>
          </hostname>
          <datesplit>-</datesplit>
          <dateformat>DD-MM-YYYY</dateformat>
          <timeformat>24</timeformat>
          <onstoragefull>overwrite</onstoragefull>
          <videostandard>PAL</videostandard>
          <autologout>10</autologout>
          <startupwizard>false</startupwizard>
          <smartdisplay>true</smartdisplay>
          <smarttracking>false</smarttracking>
          <previewstrategy>realtime</previewstrategy>
          <ability>
            <support_hostname>true</support_hostname>
          </ability>
        </general>
      </system>
    </content>
  </body>
</envelope>
"""


SYSTEM_ABILITY_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <system>
        <ability>
          <optional>
            <mask_0>
              <ability_wifi>1</ability_wifi>
              <ability_rtsp>1</ability_rtsp>
              <ability_snap>1</ability_snap>
              <ability_ptz>0</ability_ptz>
              <ability_ptz_preset>0</ability_ptz_preset>
              <ability_https>1</ability_https>
              <ability_ntp>1</ability_ntp>
              <ability_cloud>1</ability_cloud>
              <ability_cloudstorage>0</ability_cloudstorage>
              <ability_cloud_upgrade>1</ability_cloud_upgrade>
              <ability_automatic_ip>1</ability_automatic_ip>
            </mask_0>
          </optional>
          <talk>
            <ability>1</ability>
          </talk>
          <alarm>
            <alarmability>
              <motiondetection>1</motiondetection>
              <alarmin>0</alarmin>
              <videolost>1</videolost>
              <videoshelter>0</videoshelter>
            </alarmability>
          </alarm>
        </ability>
      </system>
    </content>
  </body>
</envelope>
"""


VIDEO_CONFIG_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <channel>
        <id>1</id>
        <name>Door</name>
        <ability>1</ability>
        <encode_new>true</encode_new>
        <videomode>PAL</videomode>
        <protocol>private</protocol>
        <mainstream>
          <videoformat>
            <enabled>true</enabled>
            <compression>
              <value>H.264</value>
              <supported>H.264;H.265</supported>
            </compression>
            <resolution>
              <value>1920x1080</value>
              <supported>1920x1080;960x576</supported>
            </resolution>
            <bitrate>
              <value>2048</value>
              <supported>512;1024;2048</supported>
            </bitrate>
            <bitratecontrol>
              <value>CBR</value>
              <supported>CBR;VBR</supported>
            </bitratecontrol>
            <fps>
              <value>25</value>
              <range>1-25</range>
            </fps>
            <gop>
              <value>50</value>
              <range>1-100</range>
            </gop>
            <quality>
              <value>4</value>
              <supported>1;2;3;4;5</supported>
            </quality>
          </videoformat>
          <audioformat>
            <enabled>true</enabled>
          </audioformat>
          <h264plus>
            <enabled>false</enabled>
          </h264plus>
        </mainstream>
        <substream>
          <videoformat>
            <enabled>true</enabled>
            <compression>
              <value>H.264</value>
            </compression>
            <resolution>
              <value>960x576</value>
            </resolution>
            <bitrate>
              <value>512</value>
            </bitrate>
            <fps>
              <value>15</value>
            </fps>
          </videoformat>
        </substream>
      </channel>
    </content>
  </body>
</envelope>
"""


class DeviceCgiReadonlyTests:
    def test_build_request_xml_matches_native_body_before_header(self) -> None:
        xml_body = build_request_xml(
            command="get.product.info",
            security="",
            username="adminapp2",
            password="hashed-password",
            passwordencode="1",
        )

        root = ET.fromstring(xml_body)

        assert ["body", "header"] == [child.tag for child in root]
        assert "hashed-password" == root.findtext("./header/password")
        assert "1" == root.findtext("./header/passwordencode")
        assert "get.product.info" == root.findtext("./body/command")

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

    def test_parse_product_info(self) -> None:
        info = parse_product_info(
            parse_cgi_response("get.product.info", PRODUCT_INFO_XML)
        )

        assert "00:11:22:33:44:55" == info.mac
        assert "1.2.3" == info.version
        assert "2026-01-02" == info.release_date
        assert "IDS9483PW" == info.model

    def test_parse_time_info(self) -> None:
        info = parse_time_info(
            parse_cgi_response("get.product.time", TIME_INFO_XML)
        )

        assert "Europe/Moscow" == info.time_zone
        assert "2026-06-24 15:31:00" == info.date_time

    def test_parse_wifi_list_info(self) -> None:
        info = parse_wifi_list_info(
            parse_cgi_response("get.wifi.list", WIFI_LIST_XML)
        )

        assert ["Lab WiFi", "Open WiFi"] == [
            network.ssid for network in info.networks
        ]
        assert -42 == info.networks[0].rssi
        assert info.networks[0].is_encrypted is True
        assert info.networks[1].is_encrypted is False

    def test_parse_screen_flip_info(self) -> None:
        info = parse_screen_flip_info(
            parse_cgi_response("get.shape.mirror", SCREEN_FLIP_XML)
        )

        assert "up_down" == info.mirror
        assert "r180" == info.rotate
        assert 1 == info.state
        assert 180 == info.angle

    def test_parse_video_switch_info(self) -> None:
        info = parse_video_switch_info(
            parse_cgi_response("get.videoswitch.vionoff", VIDEO_SWITCH_XML)
        )

        assert "video_on" == info.value
        assert 1 == info.state
        assert info.is_on is True

    def test_parse_time_title_info(self) -> None:
        info = parse_time_title_info(
            parse_cgi_response("get.video.timetitle", TIME_TITLE_XML)
        )

        assert 1 == len(info.overlays)
        overlay = info.overlays[0]
        assert 1 == overlay.stream_type
        assert 960 == overlay.video_width
        assert 576 == overlay.video_height
        assert 260 == overlay.title_width
        assert 32 == overlay.title_height
        assert 20 == overlay.location_x
        assert 30 == overlay.location_y

    def test_parse_system_general_info(self) -> None:
        info = parse_system_general_info(
            parse_cgi_response("get.system.general", SYSTEM_GENERAL_XML)
        )

        assert "ru" == info.language
        assert info.auto_sync_time is True
        assert "Europe/Moscow" == info.time_zone
        assert "22058iwsv6av" == info.device_id
        assert "front-door" == info.host_name
        assert 10 == info.auto_logout
        assert info.support_host_name is True

    def test_parse_system_capabilities(self) -> None:
        info = parse_system_capabilities(
            parse_cgi_response("get.system.ability", SYSTEM_ABILITY_XML)
        )

        assert 1 == info.wifi
        assert 1 == info.rtsp
        assert 1 == info.snap
        assert 1 == info.talk
        assert 0 == info.ptz
        assert 1 == info.cloud_upgrade
        assert 1 == info.motion_detection
        assert 0 == info.video_shelter

    def test_parse_video_config_info(self) -> None:
        info = parse_video_config_info(
            parse_cgi_response("get.encode", VIDEO_CONFIG_XML)
        )

        assert 1 == len(info.channels)
        channel = info.channels[0]
        assert "1" == channel.channel_id
        assert "Door" == channel.name
        assert channel.encode_new is True
        assert ["mainstream", "substream"] == [
            stream.name for stream in channel.streams
        ]
        main_stream = channel.streams[0]
        assert main_stream.enabled is True
        assert "H.264" == main_stream.compression
        assert "1920x1080" == main_stream.resolution
        assert 2048 == main_stream.bitrate
        assert "CBR" == main_stream.bitrate_control
        assert 25 == main_stream.fps
        assert 50 == main_stream.gop
        assert 4 == main_stream.quality
        assert main_stream.audio_enabled is True
        assert main_stream.h264plus_enabled is False
