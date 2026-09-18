"""Timezone helpers. London is Australia/Brisbane (AEST, UTC+10). NY is America/New_York."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

AEST = ZoneInfo("Australia/Brisbane")
NY = ZoneInfo("America/New_York")


def to_aest(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=AEST)
    return ts.astimezone(AEST)


def to_tz(ts: datetime, tz: ZoneInfo) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=tz)
    return ts.astimezone(tz)


def parse_clock(value: str) -> time:
    hours, minutes = value.split(":")[:2]
    return time(int(hours), int(minutes))


def on_clock(
    ts: datetime,
    start: time,
    end: time,
    tz: ZoneInfo | None = None,
    *,
    end_exclusive: bool = False,
) -> bool:
    local = to_tz(ts, tz or AEST).timetz().replace(tzinfo=None)
    if end_exclusive:
        return start <= local < end
    return start <= local <= end


def aest_date(ts: datetime):
    return to_aest(ts).date()


def iso(ts: datetime) -> str:
    return to_aest(ts).isoformat()
