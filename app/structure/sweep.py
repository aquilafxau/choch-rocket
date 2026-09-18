"""Asia/session liquidity sweep. No sweep = no trade.

Asia high/low is computed per AEST session day (the calendar date of the
current bar, or an explicit ``session_day``). A pierce of that day's range
can fire once that session; it must not latch onto the first pierce of a
multi-day series or fold every Asia bar into one mega high/low.
"""

from __future__ import annotations

from datetime import date, datetime, time

from app.config import Settings
from app.models import Bar, SweepEvent
from app.timeutil import aest_date, on_clock, to_aest


def _aest_clock(ts: datetime) -> time:
    return to_aest(ts).timetz().replace(tzinfo=None)


def _session_day(bars: list[Bar], session_day: date | None) -> date | None:
    if session_day is not None:
        return session_day
    if not bars:
        return None
    return aest_date(bars[-1].ts)


def asia_range(
    bars: list[Bar],
    settings: Settings,
    session_day: date | None = None,
) -> tuple[float, float, list[Bar]] | None:
    """Asia H/L for one AEST session day (default: date of the last bar).

    Only bars whose AEST date equals ``session_day`` and whose clock falls
    inside the Asia window are used. Aggregating every Asia-window bar across
    full history produced a mega range and pinned month-scale replay to day 1.
    """
    day = _session_day(bars, session_day)
    if day is None:
        return None
    start, end = settings.asia_window
    asia = [b for b in bars if aest_date(b.ts) == day and on_clock(b.ts, start, end)]
    if len(asia) < 4:
        return None
    return max(b.high for b in asia), min(b.low for b in asia), asia


def find_sweep(
    bars: list[Bar],
    settings: Settings,
    session_day: date | None = None,
) -> SweepEvent | None:
    """First post-Asia pierce of *this* session day's Asia range.

    Post-Asia means AEST clock after ``asia_end`` on the same session day.
    Earlier days' pierces are ignored so a multi-day CSV can fire once per
    eligible day instead of staying pinned to the first pierce in history.
    """
    day = _session_day(bars, session_day)
    if day is None:
        return None
    rng = asia_range(bars, settings, day)
    if rng is None:
        return None
    asia_high, asia_low, _asia = rng
    _, asia_end = settings.asia_window
    post = [b for b in bars if aest_date(b.ts) == day and _aest_clock(b.ts) > asia_end]
    if not post:
        return None

    for bar in post:
        if bar.high > asia_high + 1e-9:
            return SweepEvent(
                kind="high",
                ts=bar.ts,
                extreme=bar.high,
                asia_high=asia_high,
                asia_low=asia_low,
            )
        if bar.low < asia_low - 1e-9:
            return SweepEvent(
                kind="low",
                ts=bar.ts,
                extreme=bar.low,
                asia_high=asia_high,
                asia_low=asia_low,
            )
    return None
