import hashlib
import json

from quii_helper.device.http.json import build_common_json_request
from quii_helper.device.json_cgi import (
    COMMAND_GET_ALARM_DETAIL_INFO,
    COMMAND_GET_ALARM_STATUS,
    COMMAND_GET_AUDIO_SESSION,
    COMMAND_GET_AUDIO_VOLUME,
    COMMAND_GET_BABYSITTER_STATE,
    COMMAND_GET_CITY_COORDINATE,
    COMMAND_GET_FLOODLIGHT_SCHEDULE,
    COMMAND_GET_FLOODLIGHT_SWITCH,
    COMMAND_GET_HARDWARE,
    COMMAND_GET_JSON_FPS_MODE,
    COMMAND_GET_LIGHT_INFO,
    COMMAND_GET_LOCK_STATUS,
    COMMAND_GET_PIR_CONFIG,
    COMMAND_GET_SMART_SWITCH_INFO,
    COMMAND_GET_THIRD_PARTY_PUSH_INFO,
    COMMAND_GET_VOICE_MESSAGE,
    request_alarm_detail_info,
    request_alarm_status_info,
    request_audio_session_info,
    request_audio_volume_info,
    request_babysitter_state_info,
    request_city_coordinate_info,
    request_floodlight_schedule_info,
    request_floodlight_switch_info,
    request_hardware_info,
    request_json_fps_mode_info,
    request_light_info,
    request_lock_status_info,
    request_pir_config_info,
    request_smart_switch_info,
    request_third_party_push_info,
    request_voice_message_info,
)
from quii_helper.device.json_cgi.client import (
    request_readonly_json_cgi,
)
from quii_helper.device.json_cgi.parser import (
    parse_alarm_detail_info,
    parse_alarm_status_info,
    parse_audio_session_info,
    parse_audio_volume_info,
    parse_babysitter_state_info,
    parse_city_coordinate_info,
    parse_floodlight_schedule_info,
    parse_floodlight_switch_info,
    parse_hardware_info,
    parse_json_cgi_response,
    parse_json_fps_mode_info,
    parse_light_info,
    parse_lock_status_info,
    parse_pir_config_info,
    parse_smart_switch_info,
    parse_third_party_push_info,
    parse_voice_message_info,
)

VOLUME_JSON = {
    "body": {
        "error": 0,
        "content": {
            "prompt": {"level": 7, "min_level": 0, "max_level": 10},
            "talk": {"level": 4, "min_level": 0, "max_level": 10},
        },
    }
}

AUDIO_SESSION_JSON = {
    "body": {
        "error": 0,
        "content": {
            "session": "audio-session-id",
            "fileid": "voice-file-id",
        },
    }
}

ALARM_DETAIL_JSON = {
    "body": {
        "error": 0,
        "content": {
            "alarmtype": 2,
            "config": {
                "channel": {
                    "id": 1,
                    "enabled": 1,
                    "sensitivity": 4,
                    "max_sensitivity": 5,
                    "move_enabled": 0,
                    "record_enabled": 1,
                    "alarmlight_enabled": 0,
                    "whistle_enabled": 1,
                    "only_track": 0,
                    "record_latch": 10,
                    "schedule_mode": "custom",
                    "interval": {"value": 30, "range": [5, 60]},
                    "levellist": [
                        {"id": 1, "value": 20},
                        {"id": 2, "value": 40},
                    ],
                    "region": {
                        "rownum": 2,
                        "colnum": 3,
                        "datalist": [{"data": "111"}, {"data": "000"}],
                    },
                    "smart_filter": {"peds": 1, "vehc": 0},
                    "schedule": [
                        {
                            "week": "tuesday",
                            "time": [
                                {
                                    "section": "time1",
                                    "enabled": 1,
                                    "start": "09:00",
                                    "end": "17:00",
                                }
                            ],
                        }
                    ],
                }
            },
        },
    }
}

ALARM_STATUS_JSON = {
    "body": {
        "error": 0,
        "content": {
            "status": "on",
        },
    }
}

HARDWARE_JSON = {
    "body": {
        "error": 0,
        "content": {
            "batQuantity": 87,
            "voltameterTemp": 253,
            "chargeSource": 2,
            "chargeStatus": 1,
        },
    }
}

LIGHT_JSON = {
    "body": {
        "error": 0,
        "content": {
            "room": [
                {
                    "number": 1,
                    "name": "Hall",
                    "lights": [
                        {
                            "number": 2,
                            "name": "Main",
                            "status": 1,
                            "brightness": 75,
                        }
                    ],
                }
            ]
        },
    }
}

PIR_JSON = {
    "body": {
        "error": 0,
        "content": {
            "enabled": 1,
            "sensitivity": 42,
            "linkRecord": 0,
            "schedule": [
                {
                    "week": "monday",
                    "time": [
                        {
                            "section": "time1",
                            "enabled": 1,
                            "start": "08:00",
                            "end": "18:00",
                        }
                    ],
                }
            ],
        },
    }
}

THIRD_PARTY_PUSH_JSON = {
    "body": {
        "error": 0,
        "content": {
            "account": "door@example.com",
            "areacode": "+7",
            "pushenable": 1,
            "thirdpartytype": 2,
            "uploadtype": 3,
            "eventtype": [2, "19"],
            "supporteventtype": [2, 19, 20],
            "schedule": [
                {
                    "week": "wednesday",
                    "time": [
                        {
                            "section": "time1",
                            "enabled": 1,
                            "start": "10:00",
                            "end": "20:00",
                        }
                    ],
                }
            ],
        },
    }
}

LOCK_JSON = {
    "body": {
        "error": 0,
        "content": {
            "lock": [
                {
                    "id": 1,
                    "name": "Main lock",
                    "time": {"min": 1.0, "max": 10.0, "value": 3.5},
                }
            ]
        },
    }
}

FLOODLIGHT_JSON = {
    "body": {
        "error": 0,
        "content": {
            "light": [
                {
                    "code": "floodlight-1",
                    "status": "auto",
                    "brightness": 80,
                    "duration": 30,
                }
            ]
        },
    }
}

FLOODLIGHT_SCHEDULE_JSON = {
    "body": {
        "error": 0,
        "content": {
            "suntime": {
                "sunrise": "06:10:00",
                "sunset": "20:45:00",
            },
            "schedule": {
                "day": [
                    {
                        "week": 1,
                        "plan": [
                            {
                                "num": 1,
                                "enable": True,
                                "start": {
                                    "mode": "sunrise",
                                    "shift": 10,
                                    "time": "06:20:00",
                                },
                                "end": {
                                    "mode": "time",
                                    "shift": 0,
                                    "time": "22:00:00",
                                },
                            },
                            {
                                "num": 2,
                                "enable": False,
                                "start": {
                                    "mode": "sunset",
                                    "shift": -15,
                                    "time": "20:30:00",
                                },
                                "end": {
                                    "mode": "sunrise",
                                    "shift": 0,
                                    "time": "06:10:00",
                                },
                            },
                        ],
                    }
                ]
            },
        },
    }
}

CITY_COORDINATE_JSON = {
    "body": {
        "error": 0,
        "content": {
            "coordinate": {
                "latitude": 55.7558,
                "longitude": 37.6173,
            },
            "suntime": {
                "sunrise": "06:11:00",
                "sunset": "20:46:00",
            },
        },
    }
}

SMART_SWITCH_JSON = {
    "body": {
        "error": 0,
        "content": {
            "add_status": 1,
            "room": [
                {
                    "number": 1,
                    "name": "Hall",
                    "switchs": [
                        {
                            "number": 3,
                            "name": "Relay",
                            "online": 1,
                            "switchchntotal": 2,
                            "switchchn": [
                                {"number": 1, "name": "Left", "state": 1},
                                {"number": 2, "name": "Right", "state": 0},
                            ],
                        }
                    ],
                }
            ],
        },
    }
}

VOICE_JSON = {
    "body": {
        "error": 0,
        "content": {
            "currenrVoiceFileid": 2,
            "mode": "manul",
            "filelist": [
                {"fileid": 1, "name": "Welcome"},
                {"fileid": 2, "name": "Away"},
            ],
        },
    }
}


class DeviceJsonCgiReadOnlyTests:
    def test_build_common_json_request_matches_native_envelope(self) -> None:
        body = build_common_json_request(
            "get.audio.outvolume",
            security="username",
            username="adminapp2",
            password="encoded-password",
            passwordencode=1,
        )

        assert {
            "body": {"command": "get.audio.outvolume"},
            "header": {
                "security": "username",
                "username": "adminapp2",
                "password": "encoded-password",
                "passwordencode": 1,
            },
        } == json.loads(body)

    def test_build_common_json_request_includes_native_content(self) -> None:
        body = build_common_json_request(
            COMMAND_GET_ALARM_DETAIL_INFO,
            security="username",
            username="adminapp2",
            password="encoded-password",
            passwordencode=1,
            content={"alarmtype": 2},
        )

        assert {
            "body": {
                "command": COMMAND_GET_ALARM_DETAIL_INFO,
                "content": {"alarmtype": 2},
            },
            "header": {
                "security": "username",
                "username": "adminapp2",
                "password": "encoded-password",
                "passwordencode": 1,
            },
        } == json.loads(body)

    def test_parse_alarm_detail_info(self) -> None:
        response = parse_json_cgi_response(
            COMMAND_GET_ALARM_DETAIL_INFO,
            ALARM_DETAIL_JSON,
        )

        info = parse_alarm_detail_info(response)

        assert 0 == info.error
        assert 2 == info.alarm_type
        assert info.channel is not None
        assert 1 == info.channel.channel_id
        assert info.channel.enabled is True
        assert 4 == info.channel.sensitivity
        assert 5 == info.channel.max_sensitivity
        assert info.channel.move_enabled is False
        assert info.channel.record_enabled is True
        assert info.channel.alarm_light_enabled is False
        assert info.channel.whistle_enabled is True
        assert info.channel.only_track is False
        assert 10 == info.channel.record_latch
        assert "custom" == info.channel.schedule_mode
        assert info.channel.interval is not None
        assert 30 == info.channel.interval.value
        assert [5, 60] == info.channel.interval.range
        assert [(1, 20), (2, 40)] == [
            (level.level_id, level.value) for level in info.channel.levels
        ]
        assert info.channel.region is not None
        assert 2 == info.channel.region.row_num
        assert 3 == info.channel.region.col_num
        assert ["111", "000"] == info.channel.region.data
        assert info.channel.smart_filter is not None
        assert 1 == info.channel.smart_filter.peds
        assert 0 == info.channel.smart_filter.vehc
        assert 1 == info.channel.schedule[0].week_index
        assert "09:00" == info.channel.schedule[0].slots[0].start

    def test_parse_alarm_status_info(self) -> None:
        response = parse_json_cgi_response(
            COMMAND_GET_ALARM_STATUS,
            ALARM_STATUS_JSON,
        )

        info = parse_alarm_status_info(response)

        assert 0 == info.error
        assert "on" == info.status
        assert info.is_on is True

    def test_parse_alarm_status_info_preserves_non_on_status(self) -> None:
        response = parse_json_cgi_response(
            COMMAND_GET_ALARM_STATUS,
            {"body": {"error": 0, "content": {"status": "auto"}}},
        )

        info = parse_alarm_status_info(response)

        assert "auto" == info.status
        assert info.is_on is False

    def test_parse_audio_volume_info(self) -> None:
        response = parse_json_cgi_response(
            COMMAND_GET_AUDIO_VOLUME, VOLUME_JSON
        )

        info = parse_audio_volume_info(response)

        assert 0 == info.error
        assert info.prompt is not None
        assert 7 == info.prompt.level
        assert info.talk is not None
        assert 10 == info.talk.max_level

    def test_parse_audio_session_info(self) -> None:
        response = parse_json_cgi_response(
            COMMAND_GET_AUDIO_SESSION,
            AUDIO_SESSION_JSON,
        )

        info = parse_audio_session_info(response)

        assert 0 == info.error
        assert "audio-session-id" == info.session
        assert "voice-file-id" == info.file_id

    def test_parse_hardware_info_matches_native_mapping(self) -> None:
        response = parse_json_cgi_response(COMMAND_GET_HARDWARE, HARDWARE_JSON)

        info = parse_hardware_info(response)

        assert 0 == info.error
        assert 87 == info.battery_quantity
        assert 25.3 == info.voltmeter_temperature
        assert 2 == info.charge_source
        assert 1 == info.charge_status

    def test_parse_hardware_info_maps_unknown_native_values(self) -> None:
        response = parse_json_cgi_response(
            COMMAND_GET_HARDWARE,
            {
                "body": {
                    "error": 0,
                    "content": {
                        "chargeSource": 99,
                        "chargeStatus": 99,
                    },
                }
            },
        )

        info = parse_hardware_info(response)

        assert -1 == info.charge_source
        assert 0 == info.charge_status

    def test_parse_light_info(self) -> None:
        response = parse_json_cgi_response(COMMAND_GET_LIGHT_INFO, LIGHT_JSON)

        info = parse_light_info(response)

        assert 0 == info.error
        assert 1 == len(info.rooms)
        assert "Hall" == info.rooms[0].name
        assert 2 == info.rooms[0].lights[0].number
        assert "Main" == info.rooms[0].lights[0].name
        assert 1 == info.rooms[0].lights[0].status
        assert 75 == info.rooms[0].lights[0].brightness

    def test_parse_pir_config_info(self) -> None:
        response = parse_json_cgi_response(COMMAND_GET_PIR_CONFIG, PIR_JSON)

        info = parse_pir_config_info(response)

        assert 0 == info.error
        assert info.enabled is True
        assert 42 == info.sensitivity
        assert info.link_record is False
        assert 1 == len(info.schedule)
        assert "monday" == info.schedule[0].week
        assert 0 == info.schedule[0].week_index
        assert "time1" == info.schedule[0].slots[0].section
        assert info.schedule[0].slots[0].enabled is True
        assert "08:00" == info.schedule[0].slots[0].start
        assert "18:00" == info.schedule[0].slots[0].end

    def test_parse_third_party_push_info(self) -> None:
        response = parse_json_cgi_response(
            COMMAND_GET_THIRD_PARTY_PUSH_INFO,
            THIRD_PARTY_PUSH_JSON,
        )

        info = parse_third_party_push_info(response)

        assert 0 == info.error
        assert "door@example.com" == info.account
        assert "+7" == info.area_code
        assert info.push_enabled is True
        assert 2 == info.third_party_type
        assert 3 == info.upload_type
        assert [2, 19] == info.event_types
        assert [2, 19, 20] == info.supported_event_types
        assert 1 == len(info.schedule)
        assert "wednesday" == info.schedule[0].week
        assert 2 == info.schedule[0].week_index
        assert "time1" == info.schedule[0].slots[0].section
        assert info.schedule[0].slots[0].enabled is True
        assert "10:00" == info.schedule[0].slots[0].start
        assert "20:00" == info.schedule[0].slots[0].end

    def test_parse_json_fps_mode_info(self) -> None:
        response = parse_json_cgi_response(
            COMMAND_GET_JSON_FPS_MODE,
            {"body": {"error": 0, "content": {"mode": 2}}},
        )

        info = parse_json_fps_mode_info(response)

        assert 0 == info.error
        assert 2 == info.mode

    def test_parse_babysitter_state_info(self) -> None:
        response = parse_json_cgi_response(
            COMMAND_GET_BABYSITTER_STATE,
            {"body": {"error": 0, "content": {"mode": True}}},
        )

        info = parse_babysitter_state_info(response)

        assert 0 == info.error
        assert info.mode is True

    def test_parse_lock_status_info(self) -> None:
        response = parse_json_cgi_response(COMMAND_GET_LOCK_STATUS, LOCK_JSON)

        info = parse_lock_status_info(response)

        assert 0 == info.error
        assert 1 == len(info.locks)
        assert 1 == info.locks[0].lock_id
        assert "Main lock" == info.locks[0].name
        assert info.locks[0].time is not None
        assert 3.5 == info.locks[0].time.current

    def test_parse_floodlight_switch_info(self) -> None:
        response = parse_json_cgi_response(
            COMMAND_GET_FLOODLIGHT_SWITCH,
            FLOODLIGHT_JSON,
        )

        info = parse_floodlight_switch_info(response)

        assert 0 == info.error
        assert 1 == len(info.lights)
        assert "floodlight-1" == info.lights[0].code
        assert "auto" == info.lights[0].status
        assert 2 == info.lights[0].status_code
        assert 80 == info.lights[0].brightness
        assert 30 == info.lights[0].duration

    def test_parse_floodlight_schedule_info(self) -> None:
        response = parse_json_cgi_response(
            COMMAND_GET_FLOODLIGHT_SCHEDULE,
            FLOODLIGHT_SCHEDULE_JSON,
        )

        info = parse_floodlight_schedule_info(response)

        assert 0 == info.error
        assert "06:10:00" == info.sunrise
        assert "20:45:00" == info.sunset
        assert 1 == len(info.days)
        assert 1 == info.days[0].week
        assert 2 == len(info.days[0].plans)
        enabled_plan = info.days[0].plans[0]
        assert 1 == enabled_plan.number
        assert enabled_plan.enabled is True
        assert enabled_plan.start is not None
        assert "sunrise" == enabled_plan.start.mode
        assert 0 == enabled_plan.start.mode_code
        assert 10 == enabled_plan.start.shift
        assert "06:20:00" == enabled_plan.start.time
        assert enabled_plan.end is not None
        assert "time" == enabled_plan.end.mode
        assert 2 == enabled_plan.end.mode_code
        disabled_plan = info.days[0].plans[1]
        assert disabled_plan.enabled is False
        assert disabled_plan.start is not None
        assert "time" == disabled_plan.start.mode
        assert 2 == disabled_plan.start.mode_code
        assert 0 == disabled_plan.start.shift
        assert "00:00:00" == disabled_plan.start.time

    def test_parse_city_coordinate_info(self) -> None:
        response = parse_json_cgi_response(
            COMMAND_GET_CITY_COORDINATE,
            CITY_COORDINATE_JSON,
        )

        info = parse_city_coordinate_info(response)

        assert 0 == info.error
        assert 55.7558 == info.latitude
        assert 37.6173 == info.longitude
        assert "06:11:00" == info.sunrise
        assert "20:46:00" == info.sunset

    def test_parse_smart_switch_info(self) -> None:
        response = parse_json_cgi_response(
            COMMAND_GET_SMART_SWITCH_INFO,
            SMART_SWITCH_JSON,
        )

        info = parse_smart_switch_info(response)

        assert 0 == info.error
        assert 1 == info.add_status
        assert 1 == len(info.rooms)
        switch = info.rooms[0].switches[0]
        assert "Relay" == switch.name
        assert switch.online is True
        assert 2 == switch.switch_channel_total
        assert [True, False] == [channel.state for channel in switch.channels]

    def test_parse_voice_message_info(self) -> None:
        response = parse_json_cgi_response(
            COMMAND_GET_VOICE_MESSAGE,
            VOICE_JSON,
        )

        info = parse_voice_message_info(response)

        assert 0 == info.error
        assert 2 == info.current_file_id
        assert "manul" == info.mode
        assert 1 == info.mode_code
        assert ["Welcome", "Away"] == [item.name for item in info.files]

    def test_request_readonly_json_cgi_encodes_auth_code(
        self,
        monkeypatch,
    ) -> None:
        calls = []

        def fake_request_json_cgi(*args, **kwargs):
            calls.append((args, kwargs))
            return {"raw": VOLUME_JSON}

        monkeypatch.setattr(
            "quii_helper.device.json_cgi.client.request_json_cgi",
            fake_request_json_cgi,
        )

        response = request_readonly_json_cgi(
            COMMAND_GET_AUDIO_VOLUME,
            host="192.0.2.10",
            auth_code="auth-code",
            port=8080,
            debug=True,
        )

        assert 0 == response.error
        assert [
            (
                (COMMAND_GET_AUDIO_VOLUME,),
                {
                    "host": "192.0.2.10",
                    "port": 8080,
                    "username": "adminapp2",
                    "password": hashlib.sha256(b"auth-code").hexdigest(),
                    "encrypted": False,
                    "scheme": "http",
                    "passwordencode": 1,
                    "content": None,
                    "verify_tls": True,
                    "debug": True,
                },
            )
        ] == calls

    def test_request_specific_json_commands(self, monkeypatch) -> None:
        calls = []

        def fake_request_readonly_json_cgi(command, **kwargs):
            calls.append((command, kwargs))
            if command == COMMAND_GET_ALARM_DETAIL_INFO:
                return parse_json_cgi_response(command, ALARM_DETAIL_JSON)
            if command == COMMAND_GET_ALARM_STATUS:
                return parse_json_cgi_response(command, ALARM_STATUS_JSON)
            if command == COMMAND_GET_AUDIO_VOLUME:
                return parse_json_cgi_response(command, VOLUME_JSON)
            if command == COMMAND_GET_AUDIO_SESSION:
                return parse_json_cgi_response(command, AUDIO_SESSION_JSON)
            if command == COMMAND_GET_HARDWARE:
                return parse_json_cgi_response(command, HARDWARE_JSON)
            if command == COMMAND_GET_LIGHT_INFO:
                return parse_json_cgi_response(command, LIGHT_JSON)
            if command == COMMAND_GET_JSON_FPS_MODE:
                return parse_json_cgi_response(
                    command,
                    {"body": {"error": 0, "content": {"mode": 1}}},
                )
            if command == COMMAND_GET_LOCK_STATUS:
                return parse_json_cgi_response(command, LOCK_JSON)
            if command == COMMAND_GET_PIR_CONFIG:
                return parse_json_cgi_response(command, PIR_JSON)
            if command == COMMAND_GET_THIRD_PARTY_PUSH_INFO:
                return parse_json_cgi_response(command, THIRD_PARTY_PUSH_JSON)
            if command == COMMAND_GET_FLOODLIGHT_SWITCH:
                return parse_json_cgi_response(command, FLOODLIGHT_JSON)
            if command == COMMAND_GET_FLOODLIGHT_SCHEDULE:
                return parse_json_cgi_response(
                    command,
                    FLOODLIGHT_SCHEDULE_JSON,
                )
            if command == COMMAND_GET_CITY_COORDINATE:
                return parse_json_cgi_response(command, CITY_COORDINATE_JSON)
            if command == COMMAND_GET_SMART_SWITCH_INFO:
                return parse_json_cgi_response(command, SMART_SWITCH_JSON)
            if command == COMMAND_GET_VOICE_MESSAGE:
                return parse_json_cgi_response(command, VOICE_JSON)
            return parse_json_cgi_response(
                command,
                {"body": {"error": 0, "content": {"mode": False}}},
            )

        monkeypatch.setattr(
            "quii_helper.device.json_cgi.client.request_readonly_json_cgi",
            fake_request_readonly_json_cgi,
        )

        alarm_detail = request_alarm_detail_info(
            host="192.0.2.10",
            auth_code="auth-code",
            alarm_type=2,
        )
        alarm_status = request_alarm_status_info(
            host="192.0.2.10",
            auth_code="auth-code",
        )
        volume = request_audio_volume_info(
            host="192.0.2.10",
            auth_code="auth-code",
        )
        audio_session = request_audio_session_info(
            host="192.0.2.10",
            auth_code="auth-code",
        )
        hardware = request_hardware_info(
            host="192.0.2.10",
            auth_code="auth-code",
        )
        lights = request_light_info(
            host="192.0.2.10",
            auth_code="auth-code",
        )
        fps = request_json_fps_mode_info(
            host="192.0.2.10",
            auth_code="auth-code",
        )
        babysitter = request_babysitter_state_info(
            host="192.0.2.10",
            auth_code="auth-code",
        )
        locks = request_lock_status_info(
            host="192.0.2.10",
            auth_code="auth-code",
        )
        pir = request_pir_config_info(
            host="192.0.2.10",
            auth_code="auth-code",
        )
        third_party_push = request_third_party_push_info(
            host="192.0.2.10",
            auth_code="auth-code",
        )
        floodlight = request_floodlight_switch_info(
            host="192.0.2.10",
            auth_code="auth-code",
        )
        floodlight_schedule = request_floodlight_schedule_info(
            host="192.0.2.10",
            auth_code="auth-code",
        )
        city_coordinate = request_city_coordinate_info(
            host="192.0.2.10",
            auth_code="auth-code",
        )
        switches = request_smart_switch_info(
            host="192.0.2.10",
            auth_code="auth-code",
        )
        voice = request_voice_message_info(
            host="192.0.2.10",
            auth_code="auth-code",
        )

        assert 2 == alarm_detail.alarm_type
        assert alarm_status.is_on is True
        assert volume.prompt is not None
        assert 7 == volume.prompt.level
        assert "audio-session-id" == audio_session.session
        assert 87 == hardware.battery_quantity
        assert "Hall" == lights.rooms[0].name
        assert 1 == fps.mode
        assert babysitter.mode is False
        assert 1 == locks.locks[0].lock_id
        assert pir.enabled is True
        assert "door@example.com" == third_party_push.account
        assert "auto" == floodlight.lights[0].status
        assert "06:10:00" == floodlight_schedule.sunrise
        assert 55.7558 == city_coordinate.latitude
        assert 1 == switches.add_status
        assert 2 == voice.current_file_id
        assert [
            COMMAND_GET_ALARM_DETAIL_INFO,
            COMMAND_GET_ALARM_STATUS,
            COMMAND_GET_AUDIO_VOLUME,
            COMMAND_GET_AUDIO_SESSION,
            COMMAND_GET_HARDWARE,
            COMMAND_GET_LIGHT_INFO,
            COMMAND_GET_JSON_FPS_MODE,
            COMMAND_GET_BABYSITTER_STATE,
            COMMAND_GET_LOCK_STATUS,
            COMMAND_GET_PIR_CONFIG,
            COMMAND_GET_THIRD_PARTY_PUSH_INFO,
            COMMAND_GET_FLOODLIGHT_SWITCH,
            COMMAND_GET_FLOODLIGHT_SCHEDULE,
            COMMAND_GET_CITY_COORDINATE,
            COMMAND_GET_SMART_SWITCH_INFO,
            COMMAND_GET_VOICE_MESSAGE,
        ] == [command for command, _kwargs in calls]
        assert {"alarmtype": 2} == calls[0][1]["content"]
