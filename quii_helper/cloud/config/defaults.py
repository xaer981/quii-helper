import http.cookiejar

from quii_helper.config import constants

CLOUD_AUTH_VERSION = constants.CLOUD_AUTH_VERSION
CLOUD_COOKIE = ""
CLOUD_LOGIN_SEQ = 1

LOGIN_REQ_CLASS = "com.quvii.qvweb.userauth.bean.request.LoginReqContent"
DEVICE_TOKEN_REQ_CLASS = (
    "com.quvii.qvweb.userauth.bean.request.DevDynamicPwdGetReqContent"
)

CLOUD_COOKIE_JAR = http.cookiejar.CookieJar()
