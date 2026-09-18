"""London (AEST) and optional NY (America/New_York) session clocks."""

from __future__ import annotations

from datetime import time

from app.config import Settings
from app.models import Bar
from app.timeutil import AEST, on_clock, to_tz


def in_london(ts, settings: Settings) -> bool:
    start, end = settings.london_window
    return on_clock(ts, start, end, tz=AEST)


def in_ny(ts, settings: Settings) -> bool:
    if not settings.ny_session_enabled:
        return False
    start, end = settings.ny_window
    # SESSION_NY=09:00-12:00 → trade through 11:59, flatten at 12:00.
    exclusive = end.minute == 0 and end.second == 0
    return on_clock(ts, start, end, tz=settings.ny_zone, end_exclusive=exclusive)


def session_name(ts, settings: Settings) -> str | None:
    if in_london(ts, settings):
        return "london"
    if in_ny(ts, settings):
        return "ny"
    return None


def should_flatten(bar: Bar, settings: Settings, trade_session: str | None) -> bool:
    if trade_session == "ny":
        local = to_tz(bar.ts, settings.ny_zone).timetz().replace(tzinfo=None)
        return local >= settings.ny_flatten_time
    local = to_tz(bar.ts, AEST).timetz().replace(tzinfo=None)
    flatten: time = settings.flatten_time
    return local >= flatten
