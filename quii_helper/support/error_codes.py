"""Human-readable vendor error code descriptions.

The numeric constants are taken from the decompiled vHome/QUII Java sources:
`SDKStatus`, `CgiError`, `QvNetDeviceCoreHelper.convertCgiError`,
`HttpDeviceStatus`, `QvCStatus`, and LT compatibility error classes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ErrorCodeDomain = Literal[
    "auto",
    "device_cgi",
    "sdk",
    "cloud_storage",
    "http_device",
    "lt_compat",
]


@dataclass(frozen=True)
class VendorErrorInfo:
    """One vendor-defined error code meaning."""

    code: int
    name: str
    description: str
    source: str
    aliases: tuple[str, ...] = ()
    sdk_equivalent: int | None = None


def lookup_error_codes(
    code: int | str | None,
    *,
    domain: ErrorCodeDomain = "auto",
) -> tuple[VendorErrorInfo, ...]:
    """Return known native meanings for `code`.

    Some integer values are reused by different native layers. For example,
    raw `/tdkcgi` `-4` means a CGI password error, while SDK `-4` means an
    invalid parameter. `domain="device_cgi"` therefore returns the CGI meaning
    first and includes the SDK fallback only when it is also useful.
    """

    normalized = _coerce_code(code)
    if normalized is None:
        return ()

    tables = _tables_for_domain(domain)
    result: list[VendorErrorInfo] = []
    seen: set[tuple[int, str, str]] = set()
    for table in tables:
        info = table.get(normalized)
        if info is None:
            continue
        key = (info.code, info.source, info.name)
        if key not in seen:
            seen.add(key)
            result.append(info)
    return tuple(result)


def describe_error_code(
    code: int | str | None,
    *,
    domain: ErrorCodeDomain = "auto",
) -> str:
    """Return a concise user-facing description for a native error code."""

    infos = lookup_error_codes(code, domain=domain)
    if not infos:
        return "unknown vendor error code"
    description = "; ".join(_format_info(info) for info in infos)
    if len(infos) > 1:
        return f"possible meanings: {description}"
    return description


def _coerce_code(code: int | str | None) -> int | None:
    if code is None:
        return None
    try:
        return int(code)
    except (TypeError, ValueError):
        return None


def _tables_for_domain(
    domain: ErrorCodeDomain,
) -> tuple[dict[int, VendorErrorInfo], ...]:
    if domain == "device_cgi":
        return (
            DEVICE_CGI_ERROR_CODES,
            SDK_ERROR_CODES,
            HTTP_DEVICE_STATUS_CODES,
            LT_COMPAT_ERROR_CODES,
        )
    if domain == "sdk":
        return (SDK_ERROR_CODES, DEVICE_CGI_ERROR_CODES)
    if domain == "cloud_storage":
        return (CLOUD_STORAGE_ERROR_CODES, SDK_ERROR_CODES)
    if domain == "http_device":
        return (HTTP_DEVICE_STATUS_CODES, SDK_ERROR_CODES)
    if domain == "lt_compat":
        return (LT_COMPAT_ERROR_CODES, SDK_ERROR_CODES)
    return (
        DEVICE_CGI_ERROR_CODES,
        SDK_ERROR_CODES,
        HTTP_DEVICE_STATUS_CODES,
        CLOUD_STORAGE_ERROR_CODES,
        LT_COMPAT_ERROR_CODES,
    )


def _format_info(info: VendorErrorInfo) -> str:
    aliases = f" aliases={','.join(info.aliases)}" if info.aliases else ""
    equivalent = (
        f" sdk_equivalent={info.sdk_equivalent}"
        if info.sdk_equivalent is not None
        else ""
    )
    return (
        f"{info.name}: {info.description}"
        f" [{info.source}{aliases}{equivalent}]"
    )


def _info(
    code: int,
    name: str,
    description: str,
    source: str,
    *,
    aliases: tuple[str, ...] = (),
    sdk_equivalent: int | None = None,
) -> VendorErrorInfo:
    return VendorErrorInfo(
        code=code,
        name=name,
        description=description,
        source=source,
        aliases=aliases,
        sdk_equivalent=sdk_equivalent,
    )


DEVICE_CGI_ERROR_CODES: dict[int, VendorErrorInfo] = {
    -46: _info(
        -46,
        "CGI_ERROR_NOSPARINGTIME",
        "share access is outside the allowed time period",
        "CgiError",
        sdk_equivalent=-46,
    ),
    -45: _info(
        -45,
        "CGI_ERROR_NOAUTH",
        "share user has no permission for this operation",
        "CgiError",
        sdk_equivalent=-45,
    ),
    -12: _info(
        -12,
        "CGI_ERROR_PORTCONFLICT",
        "requested network port conflicts with another service",
        "CgiError",
        sdk_equivalent=-403,
    ),
    -10: _info(
        -10,
        "CGI_ERROR_SUBSETOVERLAP",
        "network subnet ranges overlap",
        "CgiError",
        aliases=("CGI_ERROR__SUBSETOVERLAP",),
        sdk_equivalent=-402,
    ),
    -8: _info(
        -8,
        "CGI_ERROR_ACCOUNT_INACTIVE",
        "account is inactive",
        "CgiError",
        sdk_equivalent=-35,
    ),
    -7: _info(
        -7,
        "CGI_ERROR_IP_BLOCKING",
        "client IP is blocked by the device",
        "CgiError",
        sdk_equivalent=-401,
    ),
    -6: _info(
        -6,
        "CGI_ERROR_OVER_USERNUMMAX",
        "maximum number of users/connections exceeded",
        "CgiError",
        sdk_equivalent=-400,
    ),
    -5: _info(
        -5,
        "CGI_USERNAME_LOGINED",
        "user is already logged in or relogin is required",
        "CgiError",
        sdk_equivalent=-31,
    ),
    -4: _info(
        -4,
        "CGI_ERROR_PASSWORD",
        "device password is incorrect",
        "CgiError",
        sdk_equivalent=-29,
    ),
    -3: _info(
        -3,
        "CGI_ERROR_USERNAME",
        "device username/account is invalid",
        "CgiError",
        sdk_equivalent=-30,
    ),
    -2: _info(
        -2,
        "CGI_ERROR_BLOCKEDLIST",
        "client is in the device block list",
        "CgiError",
        sdk_equivalent=-33,
    ),
    -1: _info(
        -1,
        "CGI_FAIL",
        "generic CGI command failure",
        "CgiError",
    ),
    0: _info(0, "CGI_OK", "success", "CgiError"),
    1: _info(
        1,
        "CGI_NOT_SUPPORT",
        "CGI command is not supported by this device",
        "CgiError",
        sdk_equivalent=-10,
    ),
}


SDK_ERROR_CODES: dict[int, VendorErrorInfo] = {
    -10042: _info(
        -10042,
        "FAIL_FORMAT_SD_CARD_FAILED_USING",
        "SD card format failed because the card is in use",
        "SDKStatus",
    ),
    -10041: _info(
        -10041,
        "FAIL_DEVICE_LOCK_DISABLE",
        "device lock is disabled",
        "SDKStatus",
    ),
    -10040: _info(
        -10040,
        "FAIL_DEVICE_CHANNEL_DISABLE",
        "device channel is disabled",
        "SDKStatus",
    ),
    -10039: _info(
        -10039,
        "FAIL_DEVICE_WAS_LOCKED",
        "device was locked",
        "SDKStatus",
    ),
    -10038: _info(
        -10038,
        "FAIL_DATA_PARSING_FAIL",
        "data parsing failed",
        "SDKStatus",
    ),
    -10037: _info(
        -10037,
        "FAIL_DEVICE_ZONE_ALARM_SETTING",
        "device zone alarm setting error",
        "SDKStatus",
    ),
    -10036: _info(
        -10036,
        "FAIL_DEVICE_RECORDING",
        "device is currently recording",
        "SDKStatus",
    ),
    -10035: _info(
        -10035,
        "FAIL_SERVICE_FAIL",
        "remote service failure",
        "SDKStatus",
    ),
    -10034: _info(
        -10034,
        "FAIL_AUTHENTICATION_FAIL",
        "authentication failed",
        "SDKStatus",
    ),
    -10033: _info(
        -10033,
        "FAIL_NO_RECORD",
        "no record was found",
        "SDKStatus",
    ),
    -10032: _info(
        -10032,
        "FAIL_CALL_WX_PAY_FAIL",
        "WeChat Pay invocation failed",
        "SDKStatus",
    ),
    -10031: _info(
        -10031,
        "FAIL_PAY_CANCELLED",
        "payment was cancelled",
        "SDKStatus",
    ),
    -10030: _info(
        -10030,
        "FAIL_DEVICE_NO_STORAGE",
        "device has no storage",
        "SDKStatus",
    ),
    -10029: _info(
        -10029,
        "FAIL_DEVICE_BUSY",
        "device is busy",
        "SDKStatus",
    ),
    -10028: _info(
        -10028,
        "FAIL_DEVICE_INCORRECT_PASSWORD",
        "device password is incorrect",
        "SDKStatus",
    ),
    -10027: _info(
        -10027,
        "FAIL_INSUFFICIENT_STORAGE_SPACE",
        "insufficient storage space",
        "SDKStatus",
    ),
    -10026: _info(
        -10026,
        "FAIL_FUNCTION_LOCK_OUT",
        "function is locked out",
        "SDKStatus",
    ),
    -10025: _info(
        -10025,
        "FAIL_FUNCTION_NOT_SUPPORT",
        "function is not supported",
        "SDKStatus",
    ),
    -10024: _info(
        -10024,
        "FAIL_SUB_DEVICE_OFFLINE",
        "sub-device is offline",
        "SDKStatus",
    ),
    -10023: _info(
        -10023,
        "FAIL_ENCODE_NOT_SUPPORT",
        "encoding mode is not supported",
        "SDKStatus",
    ),
    -10022: _info(
        -10022,
        "FAIL_REGION_NOT_FOUND",
        "cloud region was not found",
        "SDKStatus",
    ),
    -10021: _info(
        -10021,
        "FAIL_DATABASE_VERSION_ERROR",
        "database version error",
        "SDKStatus",
    ),
    -10020: _info(
        -10020,
        "FAIL_INVALID_REQUEST",
        "invalid request",
        "SDKStatus",
    ),
    -10019: _info(
        -10019,
        "FAIL_NO_FIND_ALARM_SERVER",
        "alarm server was not found",
        "SDKStatus",
    ),
    -10018: _info(
        -10018,
        "FAIL_AUTH_VERSION_NOT_COMPATIBLE",
        "authentication version is not compatible",
        "SDKStatus",
    ),
    -10017: _info(
        -10017,
        "FAIL_FORMAT_ERROR",
        "format error",
        "SDKStatus",
    ),
    -10016: _info(
        -10016,
        "FAIL_STATUS_ERROR",
        "invalid status",
        "SDKStatus",
    ),
    -10015: _info(
        -10015,
        "FAIL_CONNECT_SERVER_TIMEOUT",
        "server connection timed out",
        "SDKStatus",
    ),
    -10014: _info(
        -10014,
        "FAIL_NOT_ADD_DEVICE",
        "device is not added to the account",
        "SDKStatus",
    ),
    -10013: _info(
        -10013,
        "FAIL_MODE_NOT_SUPPORT",
        "mode is not supported",
        "SDKStatus",
    ),
    -10012: _info(
        -10012,
        "FAIL_RESPOND_TIMEOUT",
        "response timed out",
        "SDKStatus",
    ),
    -10011: _info(
        -10011,
        "FAIL_CONNECT_DEVICE_TIMEOUT",
        "device connection timed out",
        "SDKStatus",
    ),
    -10010: _info(
        -10010,
        "FAIL_DEVICE_AUTH_CODE_ERROR",
        "device auth code is incorrect",
        "SDKStatus",
    ),
    -10009: _info(
        -10009,
        "FAIL_ACCOUNT_NOT_EXIST",
        "account does not exist",
        "SDKStatus",
    ),
    -10008: _info(
        -10008,
        "FAIL_DEVICE_OFFLINE",
        "device is offline",
        "SDKStatus",
    ),
    -10007: _info(
        -10007,
        "FAIL_CONNECT_DEVICE_FAIL",
        "failed to connect to the device",
        "SDKStatus",
    ),
    -10006: _info(
        -10006,
        "FAIL_NO_DEVICE",
        "device was not found",
        "SDKStatus",
    ),
    -10005: _info(-10005, "FAIL_NO_LOGIN", "not logged in", "SDKStatus"),
    -10004: _info(
        -10004,
        "FAIL_ILLEGAL_INPUT",
        "illegal input",
        "SDKStatus",
    ),
    -10003: _info(
        -10003,
        "ACCOUNT_REGISTER_FAIL_ACTIVE_WAY_ERROR",
        "registration activation method is invalid",
        "SDKStatus",
    ),
    -10002: _info(
        -10002,
        "ACCOUNT_REGISTER_FAIL_MOBILE_EMPTY",
        "registration mobile number is empty",
        "SDKStatus",
    ),
    -10001: _info(
        -10001,
        "ACCOUNT_REGISTER_FAIL_EMAIL_EMPTY",
        "registration email is empty",
        "SDKStatus",
    ),
    -10000: _info(
        -10000,
        "RET_PORT_ERROR",
        "network port error",
        "SDKStatus",
    ),
    -1000: _info(
        -1000,
        "QVERR_VALIDITY",
        "validity check failed",
        "SDKStatus",
    ),
    -999: _info(
        -999,
        "ERROR_AUTH_GET_FAIL",
        "failed to obtain authentication data",
        "SDKStatus",
    ),
    -900: _info(
        -900,
        "QVERR_OPENCHANNEL",
        "failed to open channel",
        "SDKStatus",
    ),
    -700: _info(
        -700,
        "QVERR_OPENSTREAM",
        "failed to open stream",
        "SDKStatus",
    ),
    -403: _info(
        -403,
        "QVERR_PORTCONFLICT",
        "network port conflict",
        "SDKStatus",
    ),
    -402: _info(
        -402,
        "QVERR_SUBSETOVERLAP",
        "network subnet ranges overlap",
        "SDKStatus",
    ),
    -401: _info(
        -401,
        "QVERR_IP_BLOCKING",
        "client IP is blocked",
        "SDKStatus",
    ),
    -400: _info(
        -400,
        "QVERR_OVER_USERNUMMAX",
        "maximum number of users/connections exceeded",
        "SDKStatus",
    ),
    -345: _info(
        -345,
        "QVERR_ROFS",
        "filesystem is read-only",
        "SDKStatus",
    ),
    -125: _info(
        -125,
        "QVERR_DIGITAL_CHANNEL_PROTOCOL_SUPPORT",
        "digital channel protocol is not supported",
        "SDKStatus",
    ),
    -124: _info(
        -124,
        "QVERR_DIGITAL_CHANNEL_RESOURCE_LACK",
        "digital channel lacks resources",
        "SDKStatus",
    ),
    -123: _info(
        -123,
        "QVERR_DIGITAL_CHANNEL_UPGRADING",
        "digital channel is upgrading",
        "SDKStatus",
    ),
    -122: _info(
        -122,
        "QVERR_DIGITAL_CHANNEL_NO_CONNECT",
        "digital channel is not connected",
        "SDKStatus",
    ),
    -121: _info(
        -121,
        "QVERR_DIGITAL_CHANNEL_CONNECTING",
        "digital channel is connecting",
        "SDKStatus",
    ),
    -120: _info(
        -120,
        "QVERR_DIGITAL_CHANNEL_AUTHEN",
        "digital channel authentication failed",
        "SDKStatus",
    ),
    -47: _info(
        -47,
        "QVERR_BUFFER_TIMEOUT",
        "buffer timed out",
        "SDKStatus",
    ),
    -46: _info(
        -46,
        "QVERR_SHARE_NO_PERIOD",
        "share access is outside the allowed time period",
        "SDKStatus",
    ),
    -45: _info(
        -45,
        "QVERR_SHARE_NO_PERMISSION",
        "share user has no permission for this operation",
        "SDKStatus",
    ),
    -44: _info(
        -44,
        "QVERR_ZERO_CHANNEL",
        "device reports zero channels",
        "SDKStatus",
    ),
    -43: _info(
        -43,
        "QVERR_VIDEO_ENCODE",
        "video encoding error",
        "SDKStatus",
    ),
    -42: _info(-42, "QVERR_STREAM", "invalid stream", "SDKStatus"),
    -41: _info(-41, "QVERR_CHANNEL", "invalid channel", "SDKStatus"),
    -40: _info(
        -40,
        "QVERR_NO_SUPPORT_STREAM",
        "stream is not supported",
        "SDKStatus",
    ),
    -38: _info(-38, "QVERR_FS", "filesystem error", "SDKStatus"),
    -37: _info(
        -37,
        "QVERR_CAMERA_CLOSED",
        "camera is closed",
        "SDKStatus",
    ),
    -36: _info(
        -36,
        "QVERR_CUSTOMER_NUM",
        "customer/user number error",
        "SDKStatus",
    ),
    -35: _info(
        -35,
        "QVERR_INACTIVE",
        "account or device is inactive",
        "SDKStatus",
    ),
    -34: _info(
        -34,
        "QVERR_NOT_FIND_HOST",
        "host was not found",
        "SDKStatus",
    ),
    -33: _info(
        -33,
        "QVERR_BLACKLIST",
        "client is blacklisted",
        "SDKStatus",
    ),
    -32: _info(
        -32,
        "QVERR_LOCKED",
        "account or device is locked",
        "SDKStatus",
    ),
    -31: _info(
        -31,
        "QVERR_RELOGIN",
        "relogin is required",
        "SDKStatus",
    ),
    -30: _info(
        -30,
        "QVERR_ACCOUNT",
        "account is invalid",
        "SDKStatus",
    ),
    -29: _info(
        -29,
        "QVERR_PASSWORD",
        "password is incorrect",
        "SDKStatus",
    ),
    -28: _info(-28, "QVERR_NETWORK", "network error", "SDKStatus"),
    -27: _info(
        -27,
        "QVERR_BUSY",
        "device or resource is busy",
        "SDKStatus",
    ),
    -26: _info(
        -26,
        "QVERR_REMOVED",
        "resource was removed",
        "SDKStatus",
    ),
    -25: _info(-25, "QVERR_ADDRESS", "invalid address", "SDKStatus"),
    -24: _info(-24, "QVERR_FILE_READ", "file read failed", "SDKStatus"),
    -23: _info(
        -23,
        "QVERR_FOLDER_CREATE",
        "folder creation failed",
        "SDKStatus",
    ),
    -22: _info(-22, "QVERR_DISK_FULL", "disk is full", "SDKStatus"),
    -21: _info(
        -21,
        "QVERR_FILE_WRITE",
        "file write failed",
        "SDKStatus",
    ),
    -20: _info(-20, "QVERR_FILE_OPEN", "file open failed", "SDKStatus"),
    -19: _info(
        -19,
        "QVERR_CANCELLED",
        "operation was cancelled",
        "SDKStatus",
    ),
    -18: _info(-18, "QVERR_END", "end of data", "SDKStatus"),
    -17: _info(
        -17,
        "QVERR_EXISTED",
        "resource already exists",
        "SDKStatus",
    ),
    -16: _info(
        -16,
        "QVERR_AUTHEN",
        "authentication failed",
        "SDKStatus",
    ),
    -15: _info(-15, "QVERR_FORMAT", "invalid format", "SDKStatus"),
    -14: _info(-14, "QVERR_RECV", "receive failed", "SDKStatus"),
    -13: _info(-13, "QVERR_SEND", "send failed", "SDKStatus"),
    -12: _info(
        -12,
        "QVERR_RESOURCE",
        "resource error or insufficient resources",
        "SDKStatus",
    ),
    -11: _info(
        -11,
        "QVERR_FOUND",
        "requested item was not found",
        "SDKStatus",
    ),
    -10: _info(
        -10,
        "QVERR_SUPPORT",
        "operation is not supported",
        "SDKStatus",
    ),
    -9: _info(
        -9,
        "QVERR_EMPTY",
        "resource or response is empty",
        "SDKStatus",
    ),
    -8: _info(-8, "QVERR_FULL", "resource is full", "SDKStatus"),
    -7: _info(
        -7,
        "QVERR_STATE",
        "invalid state",
        "SDKStatus",
    ),
    -6: _info(
        -6,
        "QVERR_MEMORY",
        "memory allocation failed",
        "SDKStatus",
    ),
    -5: _info(-5, "QVERR_HANDLE", "invalid handle", "SDKStatus"),
    -4: _info(
        -4,
        "QVERR_PARAMETER",
        "invalid parameter",
        "SDKStatus",
    ),
    -3: _info(-3, "QVERR_PENDING", "operation is pending", "SDKStatus"),
    -2: _info(-2, "QVERR_TIMEOUT", "operation timed out", "SDKStatus"),
    -1: _info(-1, "RET_FAIL", "generic failure", "SDKStatus"),
    0: _info(0, "RET_SUCCESS", "success", "SDKStatus"),
    401: _info(
        401,
        "FAIL_DEVICE_AUTH_FAIL",
        "device authentication failed",
        "SDKStatus",
    ),
    100000: _info(
        100000,
        "EmErrSystemUnknown",
        "system error",
        "SDKStatus",
    ),
    100001: _info(
        100001,
        "EmErrSystemAbnormalNullPoint",
        "internal null-pointer error",
        "SDKStatus",
    ),
    100002: _info(
        100002,
        "EmErrCommandNotSupport",
        "command is not supported",
        "SDKStatus",
    ),
    100003: _info(
        100003,
        "EmErrMemoryMallocFailed",
        "memory allocation failed",
        "SDKStatus",
    ),
    100004: _info(
        100004,
        "EmErrRequestParseFail",
        "request parsing failed",
        "SDKStatus",
    ),
    100100000: _info(
        100100000,
        "EmErrSesionNoLogin",
        "session is not logged in",
        "SDKStatus",
    ),
    100100001: _info(
        100100001,
        "EmErrSesionIdNotConsistency",
        "session ID is inconsistent",
        "SDKStatus",
    ),
    100100002: _info(
        100100002,
        "EmErrFailedAccountNotExist",
        "account does not exist",
        "SDKStatus",
    ),
    100100003: _info(
        100100003,
        "EmErrFailedPasswordErr",
        "password is incorrect",
        "SDKStatus",
        aliases=("EmErrServerPasswordError",),
    ),
    100100004: _info(
        100100004,
        "EmErrInvalidAccountParam",
        "account parameter is invalid",
        "SDKStatus",
    ),
    100101000: _info(
        100101000,
        "EmErrLoginFailedRedirect",
        "login requires redirect",
        "SDKStatus",
    ),
    100101001: _info(
        100101001,
        "EmErrLoginFailedAccountNotActive",
        "account is not active",
        "SDKStatus",
    ),
    100101002: _info(
        100101002,
        "EmErrLoginFailedAccountLock",
        "account is locked",
        "SDKStatus",
    ),
    100101112: _info(
        100101112,
        "EmErrAuthCode",
        "auth code is incorrect",
        "SDKStatus",
    ),
    100101113: _info(
        100101113,
        "EmErrAuthCodeNotConsistencyWithMobile",
        "auth code does not match the mobile number",
        "SDKStatus",
    ),
    100101116: _info(
        100101116,
        "EmErrAuthCodeLostOrInvalid",
        "auth code is missing or invalid",
        "SDKStatus",
    ),
    100101119: _info(
        100101119,
        "EmErrMismatchOem",
        "client OEM does not match the device OEM",
        "SDKStatus",
    ),
    100101120: _info(
        100101120,
        "EmErrSendSMSFrequently",
        "SMS auth code was requested too frequently",
        "SDKStatus",
    ),
    100101121: _info(
        100101121,
        "EmErrUnknownEncWay",
        "unknown encryption method",
        "SDKStatus",
    ),
    100101122: _info(
        100101122,
        "EmErrUnSupportedOemId",
        "OEM id is not supported",
        "SDKStatus",
    ),
    100101128: _info(
        100101128,
        "EmErrDeviceHasBeenBinded",
        "device has already been bound",
        "SDKStatus",
    ),
    100101130: _info(
        100101130,
        "EmErrRegisterJoinAccountConflict",
        "associated registered account conflict",
        "SDKStatus",
    ),
    100101141: _info(
        100101141,
        "EmErrRefreshTokenLostOrIllegalClientId",
        "refresh token is missing or client id is invalid",
        "SDKStatus",
    ),
    100101142: _info(
        100101142,
        "EmErrRefreshTokenFailed",
        "refresh token request failed",
        "SDKStatus",
    ),
    100101143: _info(
        100101143,
        "EmErrTokenExpire",
        "token expired",
        "SDKStatus",
    ),
    100108000: _info(
        100108000,
        "EmErrTransparentResponseExtCodeMsg",
        "third-party transparent response error",
        "SDKStatus",
    ),
    100150000: _info(
        100150000,
        "EmErrRequestToAuthServer",
        "auth server request failed",
        "SDKStatus",
    ),
    100150001: _info(
        100150001,
        "EmErrRequestToAuthServerCacheFailed",
        "auth server cache request failed",
        "SDKStatus",
    ),
    100150002: _info(
        100150002,
        "EmErrRequestToAuthServerTimeOut",
        "auth server request timed out",
        "SDKStatus",
    ),
    100151000: _info(
        100151000,
        "EmErrServerUCommandNotSupport",
        "user server command is not supported",
        "SDKStatus",
    ),
    100151001: _info(
        100151001,
        "EmErrServerUNoBindInfo",
        "server has no device binding info",
        "SDKStatus",
    ),
    100151002: _info(
        100151002,
        "EmErrServerUSessionIllegal",
        "server session is invalid",
        "SDKStatus",
    ),
    100151004: _info(
        100151004,
        "EmErrServerUSessionNotExist",
        "server session does not exist",
        "SDKStatus",
    ),
    100152002: _info(
        100152002,
        "EmErrServerDDeviceBinded",
        "server reports device already bound",
        "SDKStatus",
    ),
    100152003: _info(
        100152003,
        "EmErrServerDDeviceAuthCode",
        "server reports invalid device auth code",
        "SDKStatus",
    ),
    100152004: _info(
        100152004,
        "EmErrServerDNoDevice",
        "server reports no such device",
        "SDKStatus",
    ),
    100152005: _info(
        100152005,
        "EmErrServerDDeviceNeverOnline",
        "server reports device has never been online",
        "SDKStatus",
    ),
}


HTTP_DEVICE_STATUS_CODES: dict[int, VendorErrorInfo] = {
    -103: _info(
        -103,
        "DEVICE_FORMAT_FAIL",
        "device storage format failed",
        "HttpDeviceStatus",
    ),
    -102: _info(
        -102,
        "DEVICE_FORMAT_FAIL_ID_NULL",
        "device storage format failed because disk id is missing",
        "HttpDeviceStatus",
    ),
    -101: _info(
        -101,
        "DEVICE_FORMAT_FAIL_RESPOND_NULL",
        "device storage format failed because response is empty",
        "HttpDeviceStatus",
    ),
    -4: _info(
        -4,
        "DEVICE_PASSWORD_ERROR",
        "device password is incorrect",
        "HttpDeviceStatus",
    ),
    100: _info(
        100,
        "DEVICE_FORMAT_FORMATTING",
        "device storage format is in progress",
        "HttpDeviceStatus",
    ),
    101: _info(
        101,
        "DEVICE_FORMAT_SUCCESS",
        "device storage format completed successfully",
        "HttpDeviceStatus",
    ),
}


CLOUD_STORAGE_ERROR_CODES: dict[int, VendorErrorInfo] = {
    310101001: _info(
        310101001,
        "FAIL_CS_DATA_IS_EXIST",
        "cloud storage data already exists",
        "QvCStatus",
    ),
    310101002: _info(
        310101002,
        "FAIL_CS_REMOTE_SERVICE_ERROR",
        "cloud storage remote service error",
        "QvCStatus",
    ),
    310101003: _info(
        310101003,
        "FAIL_CS_ORDER_CHECK_FAIL",
        "cloud storage order verification failed",
        "QvCStatus",
    ),
    310101005: _info(
        310101005,
        "FAIL_CS_REACHED_MAX_NUM",
        "cloud storage maximum count reached",
        "QvCStatus",
    ),
    310101006: _info(
        310101006,
        "FAIL_CS_PKG_END_OF_TRY",
        "cloud storage trial package has ended",
        "QvCStatus",
    ),
    310101007: _info(
        310101007,
        "FAIL_CS_PKG_END_OF_USE",
        "cloud storage package has expired",
        "QvCStatus",
    ),
    310101008: _info(
        310101008,
        "FAIL_CS_DEV_IS_BOUND_OTHER_PKG",
        "device is bound to another cloud storage package",
        "QvCStatus",
    ),
    310101009: _info(
        310101009,
        "FAIL_CS_DEV_IS_NOT_FOUND",
        "cloud storage device was not found",
        "QvCStatus",
    ),
    310101010: _info(
        310101010,
        "FAIL_CS_PKG_IS_NOT_FOUND",
        "cloud storage package was not found",
        "QvCStatus",
    ),
    310101011: _info(
        310101011,
        "FAIL_CS_DEV_HAD_BINDING",
        "device is already bound to cloud storage",
        "QvCStatus",
    ),
    310101012: _info(
        310101012,
        "FAIL_CS_DEV_INVALID",
        "cloud storage device is invalid",
        "QvCStatus",
    ),
    310101013: _info(
        310101013,
        "FAIL_CS_PKG_HAS_MODIFIED",
        "cloud storage package has been modified",
        "QvCStatus",
    ),
    310101014: _info(
        310101014,
        "FAIL_CS_RES_NOT_FOUND",
        "cloud storage resource was not found",
        "QvCStatus",
    ),
}


LT_COMPAT_ERROR_CODES: dict[int, VendorErrorInfo] = {
    -5400: _info(
        -5400,
        "GLNK_CONN_NO_NETWORK",
        "no network connection",
        "ErrorCodeToStr",
    ),
    -5304: _info(
        -5304,
        "GLNK_CONN_TO_DOMAIN",
        "domain connection failed",
        "ErrorCodeToStr",
    ),
    -5303: _info(
        -5303,
        "GLNK_CONN_GOO_NXDOMAIN",
        "GOO domain does not resolve",
        "ErrorCodeToStr",
    ),
    -5300: _info(
        -5300,
        "GLNK_CONN_LBS_NXDOMAIN",
        "LBS domain does not resolve",
        "ErrorCodeToStr",
    ),
    -5299: _info(
        -5299,
        "GLNK_CONN_LBS_ERR",
        "LBS service error",
        "ErrorCodeToStr",
    ),
    -5001: _info(
        -5001,
        "GLNK_CONN_NO_UDPFWDSVR",
        "UDP forward server was not found",
        "ErrorCodeToStr",
    ),
    -5000: _info(
        -5000,
        "GLNK_CONN_NO_FWDSVR",
        "forward server was not found",
        "ErrorCodeToStr",
    ),
    -4113: _info(
        -4113,
        "GLNK_CONN_HOST_UNREACH",
        "host is unreachable",
        "ErrorCodeToStr",
    ),
    -4111: _info(
        -4111,
        "GLNK_CONN_REFUSED",
        "connection refused",
        "ErrorCodeToStr",
    ),
    -4110: _info(
        -4110,
        "GLNK_CONN_TIMEDOUT",
        "connection timed out",
        "ErrorCodeToStr",
    ),
    -4101: _info(
        -4101,
        "GLNK_CONN_NET_UNREACH",
        "network is unreachable",
        "ErrorCodeToStr",
    ),
    -4000: _info(
        -4000,
        "GLNK_CONN_SYS_ERRNO",
        "system socket error",
        "ErrorCodeToStr",
    ),
    2: _info(
        2,
        "GLNK_AUTH_USER_PWD_ERROR",
        "username or password is incorrect",
        "ErrorCodeToStr",
    ),
    4: _info(
        4,
        "GLNK_AUTH_PDA_VERSION_ERROR",
        "client version is not compatible",
        "ErrorCodeToStr",
    ),
    5: _info(
        5,
        "GLNK_AUTH_MAX_USER_ERROR",
        "maximum number of users exceeded",
        "ErrorCodeToStr",
    ),
    6: _info(
        6,
        "GLNK_AUTH_DEVICE_OFFLINE",
        "device is offline",
        "ErrorCodeToStr",
    ),
    7: _info(
        7,
        "GLNK_AUTH_DEVICE_HAS_EXIST",
        "device already exists",
        "ErrorCodeToStr",
    ),
    8: _info(
        8,
        "GLNK_AUTH_DEVICE_OVERLOAD",
        "device is overloaded",
        "ErrorCodeToStr",
    ),
    9: _info(
        9,
        "GLNK_AUTH_INVALID_CHANNLE",
        "invalid channel",
        "ErrorCodeToStr",
        aliases=("_RESPONSECODE_INVALID_CHANNLE",),
    ),
    10: _info(
        10,
        "GLNK_AUTH_PROTOCOL_ERROR",
        "protocol error",
        "ErrorCodeToStr",
        aliases=("_RESPONSECODE_PROTOCOL_ERROR",),
    ),
    11: _info(
        11,
        "GLNK_AUTH_NOT_START_ENCODE",
        "encoding has not started",
        "ErrorCodeToStr",
    ),
    12: _info(
        12,
        "GLNK_AUTH_TASK_DISPOSE_ERROR",
        "task disposal error",
        "ErrorCodeToStr",
    ),
    13: _info(
        13,
        "GLNK_AUTH_CONFIG_ERROR",
        "configuration error",
        "ErrorCodeToStr",
    ),
    14: _info(
        14,
        "GLNK_AUTH_NOT_SUPPORT_TALK",
        "talk is not supported",
        "ErrorCodeToStr",
    ),
    17: _info(
        17,
        "GLNK_AUTH_MEMORY_ERROR",
        "memory error",
        "ErrorCodeToStr",
    ),
    18: _info(
        18,
        "GLNK_AUTH_QUERY_ERROR",
        "query error",
        "ErrorCodeToStr",
    ),
    19: _info(
        19,
        "GLNK_AUTH_NO_USER_ERROR",
        "user does not exist",
        "ErrorCodeToStr",
    ),
    20: _info(
        20,
        "GLNK_AUTH_NOW_EXITING",
        "device/session is exiting",
        "ErrorCodeToStr",
    ),
    21: _info(
        21,
        "GLNK_AUTH_GET_DATA_FAIL",
        "failed to get data",
        "ErrorCodeToStr",
    ),
    22: _info(
        22,
        "GLNK_AUTH_RIGHT_ERROR",
        "permission error",
        "ErrorCodeToStr",
    ),
    23: _info(
        23,
        "GLNK_AUTH_OPEN_LOCK_PWD_ERROR",
        "open-lock password is incorrect",
        "ErrorCodeToStr",
    ),
    24: _info(
        24,
        "GLNK_AUTH_NO_VIDEO",
        "no video is available",
        "ErrorCodeToStr",
    ),
    25: _info(
        25,
        "GLNK_AUTH_WIFI_CONFIG_FAILED",
        "Wi-Fi configuration failed",
        "ErrorCodeToStr",
    ),
    32: _info(
        32,
        "_RESPONSECODE_CRYPT_ERROR",
        "encryption/decryption error",
        "ErrorCodeToStr",
    ),
    2561: _info(
        2561,
        "GLNK_AUTH_ERR_PROTOCAL",
        "protocol version is not compatible",
        "ErrorCodeToStr",
        aliases=("_RESPONSECODE_ERROR_OLD_VERSION",),
    ),
    4660: _info(
        4660,
        "SWITCH_CHANNEL_FAIL",
        "failed to switch channel",
        "ErrorCodeToStr",
        aliases=("_RESPONSECODE_CHANNEL_ERROR",),
    ),
    5001: _info(
        5001,
        "GLNK_CONN_OPEN_ERR",
        "connection open failed",
        "ErrorCodeToStr",
    ),
    5002: _info(
        5002,
        "GLNK_CONN_ERR",
        "connection error",
        "ErrorCodeToStr",
    ),
    5530: _info(
        5530,
        "GLNK_CONN_CLOSE_TOOFAST",
        "connection closed too fast",
        "ErrorCodeToStr",
    ),
    5540: _info(
        5540,
        "GLNK_CONN_READ_TIMEOUT",
        "read timed out",
        "ErrorCodeToStr",
    ),
    5550: _info(
        5550,
        "GLNK_CONN_DISCONNECTED",
        "connection was disconnected",
        "ErrorCodeToStr",
    ),
    6110: _info(
        6110,
        "GLNK_CONN_FWD_TIMEOUT",
        "forward server connection timed out",
        "ErrorCodeToStr",
    ),
    7110: _info(
        7110,
        "GLNK_CONN_DS_TIMEOUT",
        "DS connection timed out",
        "ErrorCodeToStr",
    ),
    7111: _info(
        7111,
        "CONN_SEE_NO_AUTH",
        "viewing is not authorized",
        "ErrorCodeToStr",
    ),
}
