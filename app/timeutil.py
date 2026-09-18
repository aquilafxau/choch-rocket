"""AEST clock helpers. London window is defined in Australia/Brisbane (UTC+10, no DST)."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

AEST = ZoneInfo("Australia/Brisbane")


def to_aest(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=AEST)
    return ts.astimezone(AEST)


def parse_clock(value: str) -> time:
    hours, minutes = value.split(":")[:2]
    return time(int(hours), int(minutes))


def on_clock(ts: datetime, start: time, end: time) -> bool:
    local = to_aest(ts).timetz().replace(tzinfo=None)
    return start <= local <= end


def aest_date(ts: datetime):
    return to_aest(ts).date()


def iso(ts: datetime) -> str:
    return to_aest(ts).isoformat()
