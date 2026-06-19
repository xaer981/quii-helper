import http.cookiejar

CLOUD_HOST = "r6-5.qvcloud.net"
CLOUD_PORT = 443
CLOUD_SCHEME = "https"
CLOUD_PATH = "/auth/user"
CLOUD_OEM_ID = "G0083"
CLOUD_APP_ID = 4083
CLOUD_CLIENT_TYPE = 3
CLOUD_AUTH_VERSION = "v1.13"
CLOUD_COOKIE = ""
CLOUD_LOGIN_SEQ = 1

LOGIN_REQ_CLASS = "com.quvii.qvweb.userauth.bean.request.LoginReqContent"
DEVICE_TOKEN_REQ_CLASS = (
    "com.quvii.qvweb.userauth.bean.request.DevDynamicPwdGetReqContent"
)

CLOUD_COOKIE_JAR = http.cookiejar.CookieJar()
