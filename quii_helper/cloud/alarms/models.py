from dataclasses import dataclass, field


@dataclass(frozen=True)
class CameraCallEvent:
    """One cloud journal entry of native event type 19 (incoming call).

    Attributes:
        record_id: Journal row id, useful for deduplication across queries.
        alarm_id: Original alarm id; distinct from the journal row id.
        device_id: Camera UID/UMID.
        channel: Native channel number, without index conversion.
        time: Vendor timestamp text; no timezone is assumed or converted.
        alarm_state: Native alarm state, not a live ringing indicator.
        message_state: Native read/message state; never modified by this API.
        message_save_type: Native message storage type.
        channel_name: Optional channel label.
        alarm_info: Optional vendor alarm description.
        source: Optional alarm source identifier.
        source_name: Optional alarm source label.
        sensor_id: Optional source sensor id.
        sensor_channel: Optional native source sensor channel.
        sensor_name: Optional source sensor label.
        record_url: Optional resource URL; may contain credentials. Not fetched.
        record_sub_url: Optional secondary resource URL. Not fetched.
    """

    record_id: str
    alarm_id: str
    device_id: str
    channel: int
    time: str
    alarm_state: int
    message_state: int
    message_save_type: int
    channel_name: str = ""
    alarm_info: str = ""
    source: str = ""
    source_name: str = ""
    sensor_id: str = ""
    sensor_channel: int | None = None
    sensor_name: str = ""
    record_url: str = field(default="", repr=False)
    record_sub_url: str = field(default="", repr=False)


@dataclass(frozen=True)
class CameraCallEventPage:
    """One read-only cloud history page, not a real-time subscription.

    Attributes:
        events: Incoming calls for the requested camera, in server order.
        max_id: Native pagination anchor. Pass with the next page;
            it is not a since-id cursor for polling new calls.
        total_count: Server-reported total record count.
        unread_count: Server-reported unread count; reading does not change it.
    """

    events: list[CameraCallEvent]
    max_id: str
    total_count: int
    unread_count: int
