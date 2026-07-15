import hashlib
import xml.etree.ElementTree as ET

from quii_helper.device.cgi.client import (
    COMMAND_GET_ALARM_CHANNEL_INFO,
    COMMAND_GET_ALARM_INPUT,
    COMMAND_GET_ALARM_INPUT_SCHEDULE,
    COMMAND_GET_ALARM_MOTION_DETECTION,
    COMMAND_GET_ALARM_MOTION_DETECTION_SCHEDULE,
    COMMAND_GET_ALARM_VIDEO_LOST,
    COMMAND_GET_ALARM_VIDEO_LOST_SCHEDULE,
    COMMAND_GET_ALARM_VIDEO_SHELTER,
    COMMAND_GET_ALARM_VIDEO_SHELTER_SCHEDULE,
    COMMAND_GET_DEVICE_ATTACHMENT_INFO,
    COMMAND_GET_FPS_INFO,
    COMMAND_GET_HUMAN_TRACE_INFO,
    COMMAND_GET_MOTION_DETECTION_INFO,
    COMMAND_GET_MOVE_DETECTION_INFO,
    COMMAND_GET_NETWORK_BASE_INFO,
    COMMAND_GET_PTZ_PRESET_INFO,
    COMMAND_GET_PTZ_STATE_INFO,
    COMMAND_GET_QR_CODE_INFO,
    COMMAND_GET_RECORD_ALARM_INFO,
    COMMAND_GET_RECORD_CONFIG_INFO,
    COMMAND_GET_RECORD_MESSAGE_INFO,
    COMMAND_GET_RECORD_SESSION_INFO,
    COMMAND_GET_SMART_LIGHT_INFO,
    COMMAND_GET_SOUND_LIGHT_INFO,
    COMMAND_GET_STORAGE_INFO,
    COMMAND_GET_STREAM_KEY_INFO,
    COMMAND_GET_TF_CARD_INFO,
    COMMAND_GET_UPGRADE_PROCESS_INFO,
    COMMAND_GET_UPGRADE_STATUS_INFO,
    COMMAND_GET_UPGRADE_VERSION_INFO,
    request_alarm_channel_info,
    request_alarm_input_info,
    request_alarm_input_schedule_info,
    request_alarm_motion_detection_info,
    request_alarm_motion_detection_schedule_info,
    request_alarm_video_lost_info,
    request_alarm_video_lost_schedule_info,
    request_alarm_video_shelter_info,
    request_alarm_video_shelter_schedule_info,
    request_fps_info,
    request_human_trace_info,
    request_move_detection_info,
    request_network_base_info,
    request_ptz_preset_info,
    request_ptz_state_info,
    request_qr_code_info,
    request_readonly_cgi,
    request_record_alarm_info,
    request_record_config_info,
    request_record_message_info,
    request_record_session_info,
    request_smart_light_info,
    request_sound_light_info,
    request_tf_card_info,
    request_upgrade_process_info,
    request_upgrade_status_info,
    request_upgrade_version_info,
)
from quii_helper.device.cgi.parser import (
    parse_alarm_channel_info,
    parse_alarm_input_info,
    parse_alarm_input_schedule_info,
    parse_alarm_motion_detection_info,
    parse_alarm_motion_detection_schedule_info,
    parse_alarm_video_lost_info,
    parse_alarm_video_lost_schedule_info,
    parse_alarm_video_shelter_info,
    parse_alarm_video_shelter_schedule_info,
    parse_cgi_response,
    parse_device_all_info,
    parse_device_attachment_info,
    parse_fps_info,
    parse_human_trace_info,
    parse_motion_detection_info,
    parse_move_detection_info,
    parse_network_base_info,
    parse_network_info,
    parse_product_info,
    parse_ptz_preset_info,
    parse_ptz_state_info,
    parse_qr_code_info,
    parse_record_alarm_info,
    parse_record_config_info,
    parse_record_message_info,
    parse_record_session_info,
    parse_screen_flip_info,
    parse_smart_light_info,
    parse_sound_light_info,
    parse_storage_info,
    parse_stream_key_info,
    parse_system_capabilities,
    parse_system_general_info,
    parse_tf_card_info,
    parse_time_info,
    parse_time_title_info,
    parse_upgrade_process_info,
    parse_upgrade_status_info,
    parse_upgrade_version_info,
    parse_video_config_info,
    parse_video_switch_info,
    parse_wifi_list_info,
)
from quii_helper.device.http.xml import build_request_xml
from quii_helper.device.security.streamkey import request_streamkey

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


TF_CARD_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <formatting>false</formatting>
      <totalsum>1024</totalsum>
      <freesum>256</freesum>
      <datalist>
        <data>
          <exist>true</exist>
          <diskid>1</diskid>
          <status>normal</status>
          <total>1024</total>
          <free>256</free>
        </data>
        <data>
          <exist>false</exist>
          <diskid>2</diskid>
          <status>nodisk</status>
          <total>0</total>
          <free>0</free>
        </data>
      </datalist>
    </content>
  </body>
</envelope>
"""


TF_CARD_FORMATTING_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <formatting>true</formatting>
      <totalsum>1024</totalsum>
      <freesum>256</freesum>
      <datalist>
        <data>
          <exist>true</exist>
          <diskid>1</diskid>
          <status>normal</status>
          <total>1024</total>
          <free>256</free>
        </data>
      </datalist>
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


NETWORK_BASE_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <network>
        <base>
          <dns>8.8.8.8</dns>
          <secondarydns>1.1.1.1</secondarydns>
          <httpport>80</httpport>
          <mediaport>34567</mediaport>
          <rtspport>554</rtspport>
          <rtspurl>rtsp://192.168.1.176/live</rtspurl>
          <handsetport>12345</handsetport>
          <maxusers>4</maxusers>
          <transfermode>true</transfermode>
          <hsdownload>false</hsdownload>
          <transferpolicy>
            <value>auto</value>
            <supported>auto;p2p;relay</supported>
          </transferpolicy>
          <ability>
            <valid>1</valid>
            <support_dhcp>1</support_dhcp>
            <support_innerip>0</support_innerip>
            <support_multi_eth>0</support_multi_eth>
          </ability>
          <lanlist>
            <lan>
              <name>eth0</name>
              <ipaddress>192.168.1.176</ipaddress>
              <subnetmask>255.255.255.0</subnetmask>
              <gateway>192.168.1.1</gateway>
              <mac>00:11:22:33:44:55</mac>
              <dhcp>true</dhcp>
              <nctype>
                <value>wired</value>
                <supported>wired;wifi</supported>
              </nctype>
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


STREAM_KEY_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <key>stream-key</key>
      <tdc>tdc-value</tdc>
      <synctime>1772404834</synctime>
    </content>
  </body>
</envelope>
"""


QR_CODE_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <qrcode>qualvision-device-qr</qrcode>
    </content>
  </body>
</envelope>
"""


RECORD_CONFIG_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <channel>
        <id>1</id>
        <recordconfig>
          <recordstream>main</recordstream>
          <prerecord>5</prerecord>
          <redundancy>true</redundancy>
          <packetlength>60</packetlength>
          <recordcontrol>schedule</recordcontrol>
          <schedule>
            <sunday>
              <time1>
                <type>standard</type>
                <start>00:00</start>
                <end>12:00</end>
              </time1>
              <time2>
                <type>md</type>
                <start>12:00</start>
                <end>23:59</end>
              </time2>
            </sunday>
            <monday>
              <time1>
                <type>alarm</type>
                <start>01:00</start>
                <end>02:00</end>
              </time1>
            </monday>
          </schedule>
        </recordconfig>
      </channel>
    </content>
  </body>
</envelope>
"""


RECORD_SESSION_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <record>
        <id>archive-session-1</id>
      </record>
    </content>
  </body>
</envelope>
"""


RECORD_MESSAGE_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <result>0</result>
      <recordlist>
        <record>
          <id>record-1</id>
          <filename>20260624_000000.h264</filename>
          <filetype>video</filetype>
          <occurtype>timing</occurtype>
          <channel>1</channel>
          <starttime>2026-06-24t00:00:00z</starttime>
          <endtime>2026-06-24t00:05:00z</endtime>
          <stream>main</stream>
          <filesize>4096</filesize>
        </record>
        <record>
          <id>record-2</id>
          <filename>20260624_010000.jpg</filename>
          <filetype>picture</filetype>
          <occurtype>event</occurtype>
          <channel>1</channel>
          <starttime>2026-06-24t01:00:00z</starttime>
          <endtime>2026-06-24t01:00:01z</endtime>
          <stream>sub</stream>
          <filesize>512</filesize>
          <url>quii://user@example/mode=file</url>
        </record>
      </recordlist>
    </content>
  </body>
</envelope>
"""


ALARM_CHANNEL_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <channel>
        <id>1</id>
        <name>Door</name>
        <channeltype>video</channeltype>
        <serialno>0</serialno>
      </channel>
      <channel>
        <id>2</id>
        <name>Alarm Input</name>
        <channeltype>alarm</channeltype>
        <serialno>5</serialno>
      </channel>
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


ATTACHMENT_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <channelinfo>
        <totalnum>2</totalnum>
        <camnum>1</camnum>
        <cctvnum>1</cctvnum>
        <ipgnum>0</ipgnum>
        <managenum>0</managenum>
        <epnum>0</epnum>
        <ability>
          <switchdirectly>1</switchdirectly>
        </ability>
        <channelList>
          <channel>
            <type>cam</type>
            <num>1</num>
            <name>Door</name>
            <monenable>1</monenable>
            <talkenable>1</talkenable>
            <cctvtype>0</cctvtype>
            <enable>1</enable>
            <lockinfo>
              <lock>
                <num>1</num>
                <name>Main lock</name>
                <enable>1</enable>
              </lock>
              <lock>
                <num>2</num>
                <name>Second lock</name>
                <enable>0</enable>
              </lock>
            </lockinfo>
          </channel>
          <channel>
            <type>cctv</type>
            <num>2</num>
            <name>Camera 2</name>
            <monenable>0</monenable>
            <talkenable>0</talkenable>
            <cctvtype>1</cctvtype>
            <enable>0</enable>
          </channel>
        </channelList>
      </channelinfo>
      <elevatorinfo>
        <enable>1</enable>
        <elevatorlist>
          <elevator>
            <number>1</number>
            <enable>1</enable>
          </elevator>
        </elevatorlist>
      </elevatorinfo>
      <alarm>
        <enable>1</enable>
        <mode>2</mode>
        <numbers>4</numbers>
      </alarm>
      <light>
        <enable>1</enable>
        <room>3</room>
        <switch>5</switch>
      </light>
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


MOTION_DETECTION_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <channel>
        <id>1</id>
        <motiondetection>
          <enabled>true</enabled>
          <sensitivity>4</sensitivity>
          <range>0,0,100,100</range>
        </motiondetection>
      </channel>
    </content>
  </body>
</envelope>
"""


ALARM_MOTION_DETECTION_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <channel>
        <id>1</id>
        <motiondetection>
          <enabled>true</enabled>
          <sensitivity>5</sensitivity>
          <pedsenable>1</pedsenable>
          <region>
            <rownum>2</rownum>
            <colnum>3</colnum>
            <datalist>
              <data>111</data>
              <data>010</data>
            </datalist>
          </region>
        </motiondetection>
      </channel>
    </content>
  </body>
</envelope>
"""


ALARM_VIDEO_LOST_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <channel>
        <id>1</id>
        <videolost>
          <enabled>true</enabled>
        </videolost>
      </channel>
    </content>
  </body>
</envelope>
"""


ALARM_VIDEO_SHELTER_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <channel>
        <id>2</id>
        <videoshelter>
          <enabled>false</enabled>
          <sensitivity>4</sensitivity>
        </videoshelter>
      </channel>
    </content>
  </body>
</envelope>
"""


ALARM_INPUT_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <channel>
        <id>1</id>
        <alarmin>
          <enabled>true</enabled>
          <type>normallyopen</type>
          <name>Door input</name>
        </alarmin>
      </channel>
      <channel>
        <id>2</id>
        <alarmin>
          <enabled>false</enabled>
          <type>normallyclosed</type>
          <name>Bell input</name>
        </alarmin>
      </channel>
    </content>
  </body>
</envelope>
"""


def _alarm_schedule_xml(alarm_type: str) -> str:
    return f"""
<envelope>
  <body>
    <error>0</error>
    <content>
      <channel>
        <id>2</id>
        <{alarm_type}>
          <schedule>
            <monday>
              <time1>
                <enabled>true</enabled>
                <start>0:0:0</start>
                <end>24:00:00</end>
              </time1>
              <time2>
                <enabled>false</enabled>
                <start>08:00:00</start>
                <end>09:00:00</end>
              </time2>
            </monday>
            <tuesday>
              <time1>
                <enabled>true</enabled>
                <start>10:00:00</start>
                <end>11:00:00</end>
              </time1>
            </tuesday>
          </schedule>
        </{alarm_type}>
      </channel>
    </content>
  </body>
</envelope>
"""


HUMAN_TRACE_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <enabled>true</enabled>
    </content>
  </body>
</envelope>
"""


MOVE_DETECTION_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <enabled>0</enabled>
    </content>
  </body>
</envelope>
"""


FPS_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <channel>
        <fps>25</fps>
        <fps>15</fps>
      </channel>
      <channel>
        <fps>20</fps>
        <fps>10</fps>
      </channel>
    </content>
  </body>
</envelope>
"""


PTZ_STATE_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <position>
        <pos_x>
          <value>25</value>
          <range>0,100</range>
        </pos_x>
        <pos_y>
          <value>75</value>
          <range>10,90</range>
        </pos_y>
      </position>
    </content>
  </body>
</envelope>
"""


PTZ_PRESET_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <presetlist>
        <preset>
          <presetid>1</presetid>
          <presetname>Door</presetname>
        </preset>
        <preset>
          <presetid>2</presetid>
          <presetname>Hall</presetname>
        </preset>
      </presetlist>
    </content>
  </body>
</envelope>
"""


UPGRADE_VERSION_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <version>V401R001B008</version>
      <releasetime>2026-07-01</releasetime>
    </content>
  </body>
</envelope>
"""


UPGRADE_VERSION_TIME_FALLBACK_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <version>V401R001B008</version>
      <time>2026-07-02</time>
    </content>
  </body>
</envelope>
"""


UPGRADE_STATUS_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <upgradestatus>4</upgradestatus>
      <version>V401R001B008</version>
      <time>2026-07-01</time>
    </content>
  </body>
</envelope>
"""


UPGRADE_PROCESS_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <process>37</process>
    </content>
  </body>
</envelope>
"""


SMART_LIGHT_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <room>2</room>
      <lightnum>2</lightnum>
      <lightinfo>
        <lightno>1</lightno>
        <name>Hall</name>
        <state>1</state>
      </lightinfo>
      <lightinfo>
        <lightno>2</lightno>
        <name>Door</name>
        <state>0</state>
      </lightinfo>
    </content>
  </body>
</envelope>
"""


SOUND_LIGHT_XML = """
<envelope>
  <body>
    <error>0</error>
    <content>
      <channel>
        <id>1</id>
        <SoundAndLightOneKeyCtrl>
          <CtrlState>1</CtrlState>
        </SoundAndLightOneKeyCtrl>
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

    def test_parse_tf_card_info(self) -> None:
        info = parse_tf_card_info(
            parse_cgi_response(COMMAND_GET_TF_CARD_INFO, TF_CARD_XML)
        )

        assert info.formatting is False
        assert 1024 == info.total_sum
        assert 256 == info.free_sum
        assert [
            (True, 1, "normal", 4, 1024, 256),
            (False, 2, "nodisk", 5, 0, 0),
        ] == [
            (
                disk.exists,
                disk.disk_id,
                disk.status_raw,
                disk.status,
                disk.total,
                disk.free,
            )
            for disk in info.disks
        ]

    def test_parse_tf_card_info_skips_disks_while_formatting(self) -> None:
        info = parse_tf_card_info(
            parse_cgi_response(
                COMMAND_GET_TF_CARD_INFO,
                TF_CARD_FORMATTING_XML,
            )
        )

        assert info.formatting is True
        assert [] == info.disks

    def test_request_tf_card_info_sends_native_simple_request(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": TF_CARD_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_tf_card_info(
            host="192.0.2.10",
            auth_code="auth-code",
            debug=True,
        )

        assert 1024 == info.total_sum
        assert COMMAND_GET_TF_CARD_INFO == calls[0][0]
        assert "content" not in calls[0][1]

    def test_parse_network_info(self) -> None:
        info = parse_network_info(
            parse_cgi_response("get.network.config", NETWORK_XML)
        )

        assert "192.168.1.176" == info.address
        assert info.dhcp is True
        assert 1 == len(info.lan_interfaces)
        assert "eth0" == info.lan_interfaces[0].name
        assert info.lan_interfaces[0].dhcp is False

    def test_parse_network_base_info(self) -> None:
        info = parse_network_base_info(
            parse_cgi_response(
                COMMAND_GET_NETWORK_BASE_INFO,
                NETWORK_BASE_XML,
            )
        )

        assert 0 == info.error
        assert "8.8.8.8" == info.dns
        assert "1.1.1.1" == info.secondary_dns
        assert 80 == info.http_port
        assert 34567 == info.media_port
        assert 554 == info.rtsp_port
        assert "rtsp://192.168.1.176/live" == info.rtsp_url
        assert 12345 == info.handset_port
        assert 4 == info.max_users
        assert info.transfer_mode is True
        assert info.hs_download is False
        assert info.ability is not None
        assert 1 == info.ability.support_dhcp
        assert 0 == info.ability.support_inner_ip
        assert info.transfer_policy is not None
        assert "auto" == info.transfer_policy.value
        assert 1 == len(info.lan_interfaces)
        lan = info.lan_interfaces[0]
        assert "eth0" == lan.name
        assert "192.168.1.176" == lan.ip_address
        assert lan.dhcp is True
        assert "wired" == lan.network_type
        assert "wired;wifi" == lan.supported_network_types

    def test_request_network_base_info_sends_native_simple_request(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": NETWORK_BASE_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_network_base_info(
            host="192.0.2.10",
            auth_code="auth-code",
            debug=True,
        )

        assert 34567 == info.media_port
        assert COMMAND_GET_NETWORK_BASE_INFO == calls[0][0]
        assert "content" not in calls[0][1]

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

    def test_parse_stream_key_info(self) -> None:
        info = parse_stream_key_info(
            parse_cgi_response(COMMAND_GET_STREAM_KEY_INFO, STREAM_KEY_XML)
        )

        assert "stream-key" == info.key
        assert "tdc-value" == info.tdc
        assert "1772404834" == info.sync_time

    def test_parse_qr_code_info(self) -> None:
        info = parse_qr_code_info(
            parse_cgi_response(COMMAND_GET_QR_CODE_INFO, QR_CODE_XML)
        )

        assert 0 == info.error
        assert "qualvision-device-qr" == info.qr_code

    def test_request_qr_code_info_sends_native_simple_request(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": QR_CODE_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_qr_code_info(
            host="192.0.2.10",
            auth_code="auth-code",
            debug=True,
        )

        assert "qualvision-device-qr" == info.qr_code
        assert COMMAND_GET_QR_CODE_INFO == calls[0][0]
        assert "content" not in calls[0][1]

    def test_parse_record_config_info(self) -> None:
        info = parse_record_config_info(
            parse_cgi_response(
                COMMAND_GET_RECORD_CONFIG_INFO,
                RECORD_CONFIG_XML,
            )
        )

        assert 0 == info.error
        assert 1 == info.channel_id
        assert "main" == info.record_stream
        assert 5 == info.prerecord
        assert info.redundancy is True
        assert 60 == info.packet_length
        assert "schedule" == info.record_control
        assert [
            (1, "standard", "00:00", "12:00"),
            (2, "md", "12:00", "23:59"),
        ] == [
            (entry.slot, entry.record_type, entry.start, entry.end)
            for entry in info.schedule["sunday"]
        ]
        assert [(1, "alarm", "01:00", "02:00")] == [
            (entry.slot, entry.record_type, entry.start, entry.end)
            for entry in info.schedule["monday"]
        ]
        assert [] == info.schedule["tuesday"]

    def test_request_record_config_info_sends_native_channel_content(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": RECORD_CONFIG_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_record_config_info(
            host="192.0.2.10",
            auth_code="auth-code",
            channel_id=3,
            debug=True,
        )

        content = calls[0][1]["content"]
        assert COMMAND_GET_RECORD_CONFIG_INFO == calls[0][0]
        assert isinstance(content, ET.Element)
        assert "channel" == content.tag
        assert "3" == content.text
        assert 1 == info.channel_id

    def test_parse_record_session_info(self) -> None:
        info = parse_record_session_info(
            parse_cgi_response(
                COMMAND_GET_RECORD_SESSION_INFO,
                RECORD_SESSION_XML,
            )
        )

        assert 0 == info.error
        assert "archive-session-1" == info.session_id

    def test_request_record_session_info_sends_native_record_content(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": RECORD_SESSION_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_record_session_info(
            host="192.0.2.10",
            auth_code="auth-code",
            channel_id=3,
            start_time="2026-06-24T00:00:00",
            end_time="2026-06-24T23:59:59",
            file_type="video",
            occur_type="standard",
            stream="main",
            debug=True,
        )

        content = calls[0][1]["content"]
        assert COMMAND_GET_RECORD_SESSION_INFO == calls[0][0]
        assert isinstance(content, ET.Element)
        assert "record" == content.tag
        assert "video" == content.findtext("filetype")
        assert "standard" == content.findtext("occurtype")
        assert "3" == content.findtext("channel")
        assert "2026-06-24T00:00:00" == content.findtext("starttime")
        assert "2026-06-24T23:59:59" == content.findtext("endtime")
        assert "main" == content.findtext("stream")
        assert "archive-session-1" == info.session_id

    def test_parse_record_message_info(self) -> None:
        info = parse_record_message_info(
            parse_cgi_response(
                COMMAND_GET_RECORD_MESSAGE_INFO,
                RECORD_MESSAGE_XML,
            )
        )

        assert 0 == info.error
        assert 0 == info.result
        assert [
            (
                "record-1",
                "20260624_000000.h264",
                "video",
                "timing",
                "1",
                "2026-06-24t00:00:00z",
                "2026-06-24t00:05:00z",
                "main",
                4096,
                "",
            ),
            (
                "record-2",
                "20260624_010000.jpg",
                "picture",
                "event",
                "1",
                "2026-06-24t01:00:00z",
                "2026-06-24t01:00:01z",
                "sub",
                512,
                "quii://user@example/mode=file",
            ),
        ] == [
            (
                record.record_id,
                record.file_name,
                record.file_type,
                record.occur_type,
                record.channel_id,
                record.start_time,
                record.end_time,
                record.stream,
                record.file_size,
                record.url,
            )
            for record in info.records
        ]
        assert "record-1" == info.records[0].raw["id"]

    def test_request_record_message_info_sends_native_record_id_content(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": RECORD_MESSAGE_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_record_message_info(
            host="192.0.2.10",
            auth_code="auth-code",
            session_id="archive-session-1",
            debug=True,
        )

        content = calls[0][1]["content"]
        assert COMMAND_GET_RECORD_MESSAGE_INFO == calls[0][0]
        assert isinstance(content, ET.Element)
        assert "record" == content.tag
        assert "archive-session-1" == content.findtext("id")
        assert ["record-1", "record-2"] == [
            record.record_id for record in info.records
        ]

    def test_parse_record_alarm_info(self) -> None:
        info = parse_record_alarm_info(
            parse_cgi_response(
                COMMAND_GET_RECORD_ALARM_INFO,
                RECORD_MESSAGE_XML,
            )
        )

        assert 0 == info.error
        assert 0 == info.result
        assert ["record-1", "record-2"] == [
            record.record_id for record in info.records
        ]

    def test_request_record_alarm_info_sends_native_record_content(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": RECORD_MESSAGE_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_record_alarm_info(
            host="192.0.2.10",
            auth_code="auth-code",
            timestamp="2026-06-24T01:00:00",
            channel_id=2,
            file_type="video",
            occur_type="alarm",
            stream="main",
            alarm_type=7,
            alarm_id="alarm-1",
            debug=True,
        )

        content = calls[0][1]["content"]
        assert COMMAND_GET_RECORD_ALARM_INFO == calls[0][0]
        assert isinstance(content, ET.Element)
        assert "record" == content.tag
        assert "video" == content.findtext("filetype")
        assert "main" == content.findtext("stream")
        assert "alarm" == content.findtext("occurtype")
        assert "2" == content.findtext("channel")
        assert "2026-06-24T01:00:00" == content.findtext("timestamp")
        assert "7" == content.findtext("alarmtype")
        assert "alarm-1" == content.findtext("alarmid")
        assert ["record-1", "record-2"] == [
            record.record_id for record in info.records
        ]

    def test_parse_alarm_channel_info(self) -> None:
        info = parse_alarm_channel_info(
            parse_cgi_response(
                COMMAND_GET_ALARM_CHANNEL_INFO,
                ALARM_CHANNEL_XML,
            )
        )

        assert 0 == info.error
        assert [
            (1, "Door", "video", 0),
            (2, "Alarm Input", "alarm", 5),
        ] == [
            (
                channel.channel_id,
                channel.name,
                channel.channel_type,
                channel.serial_no,
            )
            for channel in info.channels
        ]

    def test_request_alarm_channel_info_sends_native_empty_content(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": ALARM_CHANNEL_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_alarm_channel_info(
            host="192.0.2.10",
            auth_code="auth-code",
            debug=True,
        )

        assert COMMAND_GET_ALARM_CHANNEL_INFO == calls[0][0]
        assert "content" not in calls[0][1]
        assert ["Door", "Alarm Input"] == [
            channel.name for channel in info.channels
        ]

    def test_legacy_request_streamkey_uses_shared_parser(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": STREAM_KEY_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.security.streamkey.request_cgi",
            fake_request_cgi,
        )

        result = request_streamkey(host="192.0.2.10", debug=True)

        assert {
            "key": "stream-key",
            "tdc": "tdc-value",
            "synctime": "1772404834",
        } == result
        assert [
            (
                COMMAND_GET_STREAM_KEY_INFO,
                {"host": "192.0.2.10", "debug": True},
            )
        ] == calls

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

    def test_parse_device_attachment_info(self) -> None:
        info = parse_device_attachment_info(
            parse_cgi_response(
                COMMAND_GET_DEVICE_ATTACHMENT_INFO, ATTACHMENT_XML
            )
        )

        assert 0 == info.error
        assert info.profile is not None
        assert 2 == info.profile.total_channel_num
        assert 1 == info.profile.cam_num
        assert 1 == info.profile.cctv_num
        assert info.profile.switch_direct is True
        assert 2 == len(info.channels)
        assert "Door" == info.channels[0].name
        assert "cam" == info.channels[0].channel_type
        assert 0 == info.channels[0].sub_type
        assert info.channels[0].enabled is True
        assert info.channels[0].video_enabled is True
        assert info.channels[0].talk_enabled is True
        assert 2 == len(info.channels[0].locks)
        assert "Main lock" == info.channels[0].locks[0].name
        assert info.channels[0].locks[0].enabled is True
        assert info.channels[0].locks[1].enabled is False
        assert "cctv" == info.channels[1].channel_type
        assert 1 == info.channels[1].sub_type
        assert info.channels[1].enabled is False
        assert info.channels[1].video_enabled is False
        assert 1 == len(info.elevators)
        assert info.elevators[0].enabled is True
        assert 1 == len(info.alarms)
        assert 2 == info.alarms[0].mode
        assert 4 == info.alarms[0].numbers
        assert 1 == len(info.smart_switches)
        assert 3 == info.smart_switches[0].room
        assert 5 == info.smart_switches[0].total

    def test_parse_motion_detection_info(self) -> None:
        info = parse_motion_detection_info(
            parse_cgi_response(
                COMMAND_GET_MOTION_DETECTION_INFO, MOTION_DETECTION_XML
            )
        )

        assert 0 == info.error
        assert 1 == info.channel_id
        assert info.enabled is True
        assert 4 == info.sensitivity
        assert "0,0,100,100" == info.range

    def test_parse_alarm_motion_detection_info(self) -> None:
        info = parse_alarm_motion_detection_info(
            parse_cgi_response(
                COMMAND_GET_ALARM_MOTION_DETECTION,
                ALARM_MOTION_DETECTION_XML,
            )
        )

        assert 0 == info.error
        assert 1 == info.channel_id
        assert info.enabled is True
        assert 5 == info.sensitivity
        assert 1 == info.peds_enabled
        assert 2 == info.row_num
        assert 3 == info.col_num
        assert ["111", "010"] == info.region_data

    def test_request_alarm_motion_detection_info_sends_native_channel_content(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": ALARM_MOTION_DETECTION_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_alarm_motion_detection_info(
            host="192.0.2.10",
            auth_code="plain-auth",
            channel_id=2,
        )

        assert COMMAND_GET_ALARM_MOTION_DETECTION == calls[0][0]
        content = calls[0][1]["content"]
        assert isinstance(content, ET.Element)
        assert "channel" == content.tag
        assert "2" == content.text
        assert 1 == info.channel_id

    def test_parse_alarm_video_lost_info(self) -> None:
        info = parse_alarm_video_lost_info(
            parse_cgi_response(
                COMMAND_GET_ALARM_VIDEO_LOST,
                ALARM_VIDEO_LOST_XML,
            )
        )

        assert 0 == info.error
        assert 1 == info.channel_id
        assert info.enabled is True

    def test_parse_alarm_video_shelter_info(self) -> None:
        info = parse_alarm_video_shelter_info(
            parse_cgi_response(
                COMMAND_GET_ALARM_VIDEO_SHELTER,
                ALARM_VIDEO_SHELTER_XML,
            )
        )

        assert 0 == info.error
        assert 2 == info.channel_id
        assert info.enabled is False
        assert 4 == info.sensitivity

    def test_request_alarm_video_lost_info_sends_native_channel_content(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": ALARM_VIDEO_LOST_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_alarm_video_lost_info(
            host="192.0.2.10",
            auth_code="plain-auth",
            channel_id=2,
        )

        assert COMMAND_GET_ALARM_VIDEO_LOST == calls[0][0]
        content = calls[0][1]["content"]
        assert isinstance(content, ET.Element)
        assert "channel" == content.tag
        assert "2" == content.text
        assert info.enabled is True

    def test_request_alarm_video_shelter_info_sends_native_channel_content(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": ALARM_VIDEO_SHELTER_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_alarm_video_shelter_info(
            host="192.0.2.10",
            auth_code="plain-auth",
            channel_id=3,
        )

        assert COMMAND_GET_ALARM_VIDEO_SHELTER == calls[0][0]
        content = calls[0][1]["content"]
        assert isinstance(content, ET.Element)
        assert "channel" == content.tag
        assert "3" == content.text
        assert 4 == info.sensitivity

    def test_parse_alarm_input_info(self) -> None:
        info = parse_alarm_input_info(
            parse_cgi_response(COMMAND_GET_ALARM_INPUT, ALARM_INPUT_XML)
        )

        assert 0 == info.error
        assert 2 == len(info.channels)
        assert 1 == info.channels[0].channel_id
        assert info.channels[0].enabled is True
        assert "normallyopen" == info.channels[0].input_type
        assert "Door input" == info.channels[0].name
        assert 2 == info.channels[1].channel_id
        assert info.channels[1].enabled is False

    def test_request_alarm_input_info_all_sends_native_simple_request(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": ALARM_INPUT_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_alarm_input_info(
            host="192.0.2.10",
            auth_code="plain-auth",
        )

        assert COMMAND_GET_ALARM_INPUT == calls[0][0]
        assert "content" not in calls[0][1]
        assert ["Door input", "Bell input"] == [
            channel.name for channel in info.channels
        ]

    def test_request_alarm_input_info_channel_sends_native_channel_content(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": ALARM_INPUT_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_alarm_input_info(
            host="192.0.2.10",
            auth_code="plain-auth",
            channel_id=2,
        )

        assert COMMAND_GET_ALARM_INPUT == calls[0][0]
        content = calls[0][1]["content"]
        assert isinstance(content, ET.Element)
        assert "channel" == content.tag
        assert "2" == content.text
        assert 2 == len(info.channels)

    def test_parse_alarm_schedule_info_normalizes_native_times(self) -> None:
        info = parse_alarm_motion_detection_schedule_info(
            parse_cgi_response(
                COMMAND_GET_ALARM_MOTION_DETECTION_SCHEDULE,
                _alarm_schedule_xml("motiondetection"),
            )
        )

        assert 0 == info.error
        assert "motiondetection" == info.alarm_type
        assert 2 == info.channel_id
        monday = info.days["monday"]
        assert "monday" == monday.day
        assert [
            (1, True, "00:00:00", "23:59:59"),
            (2, False, "08:00:00", "09:00:00"),
        ] == [
            (slot.slot, slot.enabled, slot.start, slot.end)
            for slot in monday.slots
        ]
        assert [(1, "10:00:00", "11:00:00")] == [
            (slot.slot, slot.start, slot.end)
            for slot in info.days["tuesday"].slots
        ]
        assert [] == info.days["wednesday"].slots

    def test_parse_alarm_schedule_info_for_all_native_alarm_types(
        self,
    ) -> None:
        cases = [
            (
                COMMAND_GET_ALARM_MOTION_DETECTION_SCHEDULE,
                parse_alarm_motion_detection_schedule_info,
                "motiondetection",
            ),
            (
                COMMAND_GET_ALARM_VIDEO_LOST_SCHEDULE,
                parse_alarm_video_lost_schedule_info,
                "videolost",
            ),
            (
                COMMAND_GET_ALARM_VIDEO_SHELTER_SCHEDULE,
                parse_alarm_video_shelter_schedule_info,
                "videoshelter",
            ),
            (
                COMMAND_GET_ALARM_INPUT_SCHEDULE,
                parse_alarm_input_schedule_info,
                "alarmin",
            ),
        ]

        for command, parser, alarm_type in cases:
            info = parser(
                parse_cgi_response(command, _alarm_schedule_xml(alarm_type))
            )

            assert alarm_type == info.alarm_type
            assert 2 == info.channel_id
            assert 2 == len(info.days["monday"].slots)

    def test_request_alarm_schedule_info_sends_native_channel_content(
        self,
        monkeypatch,
    ) -> None:
        calls = []
        responses = {
            COMMAND_GET_ALARM_MOTION_DETECTION_SCHEDULE: _alarm_schedule_xml(
                "motiondetection"
            ),
            COMMAND_GET_ALARM_VIDEO_LOST_SCHEDULE: _alarm_schedule_xml(
                "videolost"
            ),
            COMMAND_GET_ALARM_VIDEO_SHELTER_SCHEDULE: _alarm_schedule_xml(
                "videoshelter"
            ),
            COMMAND_GET_ALARM_INPUT_SCHEDULE: _alarm_schedule_xml("alarmin"),
        }

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": responses[command], "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        infos = [
            request_alarm_motion_detection_schedule_info(
                host="192.0.2.10",
                auth_code="plain-auth",
                channel_id=2,
            ),
            request_alarm_video_lost_schedule_info(
                host="192.0.2.10",
                auth_code="plain-auth",
                channel_id=2,
            ),
            request_alarm_video_shelter_schedule_info(
                host="192.0.2.10",
                auth_code="plain-auth",
                channel_id=2,
            ),
            request_alarm_input_schedule_info(
                host="192.0.2.10",
                auth_code="plain-auth",
                channel_id=2,
            ),
        ]

        assert [
            COMMAND_GET_ALARM_MOTION_DETECTION_SCHEDULE,
            COMMAND_GET_ALARM_VIDEO_LOST_SCHEDULE,
            COMMAND_GET_ALARM_VIDEO_SHELTER_SCHEDULE,
            COMMAND_GET_ALARM_INPUT_SCHEDULE,
        ] == [command for command, _ in calls]
        assert [
            "motiondetection",
            "videolost",
            "videoshelter",
            "alarmin",
        ] == [info.alarm_type for info in infos]
        for _, kwargs in calls:
            content = kwargs["content"]
            assert isinstance(content, ET.Element)
            assert "channel" == content.tag
            assert "2" == content.text

    def test_parse_human_trace_info(self) -> None:
        info = parse_human_trace_info(
            parse_cgi_response(COMMAND_GET_HUMAN_TRACE_INFO, HUMAN_TRACE_XML)
        )

        assert 0 == info.error
        assert info.enabled is True

    def test_request_human_trace_info_sends_native_simple_request(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": HUMAN_TRACE_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_human_trace_info(
            host="192.0.2.10",
            auth_code="auth-code",
            debug=True,
        )

        assert info.enabled is True
        assert COMMAND_GET_HUMAN_TRACE_INFO == calls[0][0]
        assert "content" not in calls[0][1]

    def test_parse_move_detection_info(self) -> None:
        info = parse_move_detection_info(
            parse_cgi_response(
                COMMAND_GET_MOVE_DETECTION_INFO, MOVE_DETECTION_XML
            )
        )

        assert 0 == info.error
        assert info.enabled is False

    def test_request_move_detection_info_sends_native_simple_request(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": MOVE_DETECTION_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_move_detection_info(
            host="192.0.2.10",
            auth_code="auth-code",
            debug=True,
        )

        assert info.enabled is False
        assert COMMAND_GET_MOVE_DETECTION_INFO == calls[0][0]
        assert "content" not in calls[0][1]

    def test_parse_fps_info(self) -> None:
        info = parse_fps_info(
            parse_cgi_response(COMMAND_GET_FPS_INFO, FPS_XML)
        )

        assert 0 == info.error
        assert [
            (0, 0, 25),
            (0, 1, 15),
            (1, 0, 20),
            (1, 1, 10),
        ] == [
            (channel.channel_id, channel.stream_id, channel.fps)
            for channel in info.channels
        ]

    def test_parse_filtered_fps_info_uses_requested_indexes(self) -> None:
        info = parse_fps_info(
            parse_cgi_response(COMMAND_GET_FPS_INFO, FPS_XML),
            channel_id=1,
            stream_id=1,
        )

        assert [(1, 1, 10)] == [
            (channel.channel_id, channel.stream_id, channel.fps)
            for channel in info.channels
        ]

    def test_request_fps_info_sends_native_channel_stream_content(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": FPS_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_fps_info(
            host="192.0.2.10",
            auth_code="auth-code",
            channel_id=1,
            stream_id=0,
            debug=True,
        )

        content = calls[0][1]["content"]
        assert isinstance(content, ET.Element)
        assert "channel" == content.tag
        assert "1" == content.findtext("id")
        assert "0" == content.findtext("stream")
        assert [(1, 0, 20)] == [
            (channel.channel_id, channel.stream_id, channel.fps)
            for channel in info.channels
        ]

    def test_parse_ptz_state_info(self) -> None:
        info = parse_ptz_state_info(
            parse_cgi_response(COMMAND_GET_PTZ_STATE_INFO, PTZ_STATE_XML)
        )

        assert 25 == info.position_x
        assert 75 == info.position_y
        assert 0 == info.min_x
        assert 100 == info.max_x
        assert 10 == info.min_y
        assert 90 == info.max_y

    def test_request_ptz_state_info_sends_native_simple_request(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": PTZ_STATE_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_ptz_state_info(
            host="192.0.2.10",
            auth_code="auth-code",
            debug=True,
        )

        assert 25 == info.position_x
        assert COMMAND_GET_PTZ_STATE_INFO == calls[0][0]
        assert "content" not in calls[0][1]

    def test_parse_ptz_preset_info(self) -> None:
        info = parse_ptz_preset_info(
            parse_cgi_response(COMMAND_GET_PTZ_PRESET_INFO, PTZ_PRESET_XML)
        )

        assert [("1", "Door"), ("2", "Hall")] == [
            (preset.preset_id, preset.name) for preset in info.presets
        ]

    def test_request_ptz_preset_info_sends_native_simple_request(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": PTZ_PRESET_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_ptz_preset_info(
            host="192.0.2.10",
            auth_code="auth-code",
            debug=True,
        )

        assert ["Door", "Hall"] == [preset.name for preset in info.presets]
        assert COMMAND_GET_PTZ_PRESET_INFO == calls[0][0]
        assert "content" not in calls[0][1]

    def test_parse_upgrade_version_info(self) -> None:
        info = parse_upgrade_version_info(
            parse_cgi_response(
                COMMAND_GET_UPGRADE_VERSION_INFO,
                UPGRADE_VERSION_XML,
            )
        )

        assert "V401R001B008" == info.version
        assert "2026-07-01" == info.release_time

    def test_parse_upgrade_version_info_falls_back_to_time(self) -> None:
        info = parse_upgrade_version_info(
            parse_cgi_response(
                COMMAND_GET_UPGRADE_VERSION_INFO,
                UPGRADE_VERSION_TIME_FALLBACK_XML,
            )
        )

        assert "2026-07-02" == info.release_time

    def test_parse_upgrade_status_info(self) -> None:
        info = parse_upgrade_status_info(
            parse_cgi_response(
                COMMAND_GET_UPGRADE_STATUS_INFO,
                UPGRADE_STATUS_XML,
            )
        )

        assert 4 == info.status
        assert "V401R001B008" == info.version
        assert "2026-07-01" == info.time

    def test_parse_upgrade_process_info(self) -> None:
        info = parse_upgrade_process_info(
            parse_cgi_response(
                COMMAND_GET_UPGRADE_PROCESS_INFO,
                UPGRADE_PROCESS_XML,
            )
        )

        assert 37 == info.process

    def test_request_upgrade_info_sends_native_simple_requests(
        self,
        monkeypatch,
    ) -> None:
        calls = []
        responses = {
            COMMAND_GET_UPGRADE_VERSION_INFO: UPGRADE_VERSION_XML,
            COMMAND_GET_UPGRADE_STATUS_INFO: UPGRADE_STATUS_XML,
            COMMAND_GET_UPGRADE_PROCESS_INFO: UPGRADE_PROCESS_XML,
        }

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": responses[command], "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        version = request_upgrade_version_info(
            host="192.0.2.10",
            auth_code="auth-code",
            debug=True,
        )
        status = request_upgrade_status_info(
            host="192.0.2.10",
            auth_code="auth-code",
            debug=True,
        )
        process = request_upgrade_process_info(
            host="192.0.2.10",
            auth_code="auth-code",
            debug=True,
        )

        assert "V401R001B008" == version.version
        assert 4 == status.status
        assert 37 == process.process
        assert [
            COMMAND_GET_UPGRADE_VERSION_INFO,
            COMMAND_GET_UPGRADE_STATUS_INFO,
            COMMAND_GET_UPGRADE_PROCESS_INFO,
        ] == [command for command, _ in calls]
        assert all("content" not in kwargs for _, kwargs in calls)

    def test_parse_smart_light_info(self) -> None:
        info = parse_smart_light_info(
            parse_cgi_response(COMMAND_GET_SMART_LIGHT_INFO, SMART_LIGHT_XML)
        )

        assert 0 == info.error
        assert 2 == info.room
        assert 2 == info.light_num
        assert [
            (1, "Hall", 1),
            (2, "Door", 0),
        ] == [
            (light.light_no, light.name, light.state) for light in info.lights
        ]

    def test_request_smart_light_info_sends_native_room_content(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": SMART_LIGHT_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_smart_light_info(
            host="192.0.2.10",
            auth_code="auth-code",
            room=2,
            debug=True,
        )

        content = calls[0][1]["content"]
        assert COMMAND_GET_SMART_LIGHT_INFO == calls[0][0]
        assert isinstance(content, ET.Element)
        assert "room" == content.tag
        assert "2" == content.text
        assert 2 == info.room
        assert [(1, "Hall"), (2, "Door")] == [
            (light.light_no, light.name) for light in info.lights
        ]

    def test_parse_sound_light_info(self) -> None:
        info = parse_sound_light_info(
            parse_cgi_response(COMMAND_GET_SOUND_LIGHT_INFO, SOUND_LIGHT_XML)
        )

        assert 0 == info.error
        assert [("1", 1)] == [
            (channel.channel_id, channel.ctrl_state)
            for channel in info.channels
        ]

    def test_request_sound_light_info_sends_native_channel_content(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_cgi(
            command: str,
            **kwargs: object,
        ) -> dict[str, str]:
            calls.append((command, kwargs))
            return {"raw": SOUND_LIGHT_XML, "error": "0"}

        monkeypatch.setattr(
            "quii_helper.device.cgi.client.request_cgi",
            fake_request_cgi,
        )

        info = request_sound_light_info(
            host="192.0.2.10",
            auth_code="auth-code",
            channel_id=1,
            debug=True,
        )

        content = calls[0][1]["content"]
        assert COMMAND_GET_SOUND_LIGHT_INFO == calls[0][0]
        assert isinstance(content, ET.Element)
        assert "channel" == content.tag
        assert "1" == content.text
        assert [("1", 1)] == [
            (channel.channel_id, channel.ctrl_state)
            for channel in info.channels
        ]

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
