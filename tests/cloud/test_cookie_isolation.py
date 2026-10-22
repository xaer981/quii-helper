import urllib.request
import xml.etree.ElementTree as ET
from http.cookiejar import CookieJar

import pytest

from quii_helper import AutonomousConfig, Camera
from quii_helper.cloud.http import transport
from quii_helper.cloud.services.discovery import fetch_runtime_credentials
from tests.cloud.test_http_transport import _Response


def _config(account):
    return AutonomousConfig(
        cloud_account=account,
        cloud_password="synthetic-password",
        device_id=f"device-{account}",
        auth_url="https://auth.example/UserAuth",
        service_url="https://service.example",
        oem="OEM",
        app_id=1,
        client_type=2,
        ip_region_id=3,
        client_id=f"client-{account}",
    )


@pytest.fixture
def cloud_server(monkeypatch):
    """Run urllib cookie processing against synthetic responses, without sockets."""
    seen = []

    def build(*, verify_tls, cookie_jar):
        processor = urllib.request.HTTPCookieProcessor(cookie_jar)

        class Opener:
            def open(self, request, timeout):
                processor.https_request(request)
                root = ET.fromstring(request.data)
                command = root.findtext("header/command")
                account = root.findtext("content/account")
                session = root.findtext("header/session")
                seen.append(
                    (
                        command,
                        account,
                        session,
                        request.get_header("Cookie"),
                        cookie_jar,
                    )
                )
                if command == "login":
                    body = (
                        f"<response><header><result>0</result><session>session-{account}</session>"
                        "</header><content/></response>"
                    ).encode()
                    headers = {"Set-Cookie": f"session={account}; Path=/"}
                elif command == "get-device-token":
                    body = b"<response><header><result>0</result></header><content/></response>"
                    headers = {}
                elif command == "get-device-list":
                    body = b"<response><header><result>0</result></header><content/></response>"
                    headers = {}
                else:
                    pytest.fail(
                        f"unexpected synthetic cloud command: {command}"
                    )
                response = _Response(body, headers)
                processor.https_response(request, response)
                return response

        return Opener()

    monkeypatch.setattr(transport, "build_cloud_opener", build)
    return seen


def test_two_cameras_keep_login_token_and_device_list_cookies_separate(
    cloud_server,
):
    first, second = Camera(_config("first")), Camera(_config("second"))
    first.get_device_info()
    second.get_device_info()
    assert first.connector.cookie_jar is not second.connector.cookie_jar
    assert len(cloud_server) == 6
    for index, camera, account in ((0, first, "first"), (3, second, "second")):
        login, token, listing = cloud_server[index : index + 3]
        assert login[0] == "login" and login[3] is None
        assert (
            token[0] == "get-device-token" and token[3] == f"session={account}"
        )
        assert (
            listing[0] == "get-device-list"
            and listing[3] == f"session={account}"
        )
        assert all(
            call[4] is camera.connector.cookie_jar
            for call in (login, token, listing)
        )


def test_standalone_runtime_fetch_shares_its_flow_but_not_other_calls(
    cloud_server,
):
    for account in ("first", "second"):
        fetch_runtime_credentials(_config(account))
    first_login, first_token, second_login, second_token = cloud_server
    assert first_login[4] is first_token[4]
    assert second_login[4] is second_token[4]
    assert first_login[4] is not second_login[4]
    assert first_login[3] is None and second_login[3] is None


def test_explicit_empty_cookie_jar_is_preserved(cloud_server):
    jar = CookieJar()
    fetch_runtime_credentials(_config("first"), cookie_jar=jar)
    assert all(call[4] is jar for call in cloud_server)
    assert cloud_server[1][3] == "session=first"
