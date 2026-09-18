"""Asia/session liquidity sweep. No sweep = no trade.

Ranges are **session-scoped** to one AEST calendar day — never a mega high/low
across the whole CSV:

- **Prior Asia** ``07:00–15:59`` AEST on that day → session H/L and in-window EQH/EQL
- **Current London / post-Asia** (clock after ``asia_end`` on the same day) → hunt window

A pierce of that day's Asia H/L or of EQH/EQL formed inside that day's Asia
window can fire once per eligible session. Earlier days are ignored.
"""

from __future__ import annotations

from datetime import date, datetime, time

from app.config import Settings
from app.models import Bar, SweepEvent
from app.structure.swings import confirmed_swings
from app.timeutil import aest_date, on_clock, to_aest


def _aest_clock(ts: datetime) -> time:
    return to_aest(ts).timetz().replace(tzinfo=None)


def _session_day(bars: list[Bar], session_day: date | None) -> date | None:
    if session_day is not None:
        return session_day
    if not bars:
        return None
    return aest_date(bars[-1].ts)


def session_window_bars(
    bars: list[Bar],
    session_day: date,
    start: time,
    end: time,
    *,
    end_exclusive: bool = False,
) -> list[Bar]:
    """Bars on a single AEST session day whose clock sits in ``[start, end]``."""
    return [
        b
        for b in bars
        if aest_date(b.ts) == session_day and on_clock(b.ts, start, end, end_exclusive=end_exclusive)
    ]


def prior_asia_bars(
    bars: list[Bar],
    settings: Settings,
    session_day: date | None = None,
) -> list[Bar]:
    """Prior Asia session on the given (or current) AEST day only."""
    day = _session_day(bars, session_day)
    if day is None:
        return []
    start, end = settings.asia_window
    return session_window_bars(bars, day, start, end)


def hunt_window_bars(
    bars: list[Bar],
    settings: Settings,
    session_day: date | None = None,
) -> list[Bar]:
    """Same-day post-Asia bars (London and late NY on this AEST date)."""
    day = _session_day(bars, session_day)
    if day is None:
        return []
    _, asia_end = settings.asia_window
    return [
        b for b in bars if aest_date(b.ts) == day and _aest_clock(b.ts) > asia_end
    ]


def in_window_equal_levels(
    window: list[Bar],
    settings: Settings,
) -> tuple[float | None, float | None]:
    """EQH / EQL from confirmed swings **inside one session window**.

    Never looks at swings from other days or from the full-history series.
    """
    if len(window) < settings.swing_left + settings.swing_right + 1:
        return None, None
    swings = confirmed_swings(window, settings.swing_left, settings.swing_right)
    tol = settings.eq_tolerance
    highs = [s.price for s in swings if s.kind == "high"]
    lows = [s.price for s in swings if s.kind == "low"]
    return _paired_level(highs, tol, extreme="max"), _paired_level(lows, tol, extreme="min")


def _paired_level(prices: list[float], tol: float, *, extreme: str) -> float | None:
    best: float | None = None
    for i, left in enumerate(prices):
        for right in prices[i + 1 :]:
            if abs(left - right) > tol + 1e-12:
                continue
            level = max(left, right) if extreme == "max" else min(left, right)
            if best is None:
                best = level
            elif extreme == "max":
                best = max(best, level)
            else:
                best = min(best, level)
    return best


def asia_range(
    bars: list[Bar],
    settings: Settings,
    session_day: date | None = None,
) -> tuple[float, float, list[Bar]] | None:
    """Prior-Asia H/L for one AEST session day (default: date of the last bar).

    Only that day's Asia-window bars are used. This is not a global aggregate
    of every Asia-clock bar in the CSV.
    """
    asia = prior_asia_bars(bars, settings, session_day)
    if len(asia) < 4:
        return None
    return max(b.high for b in asia), min(b.low for b in asia), asia


def find_sweep(
    bars: list[Bar],
    settings: Settings,
    session_day: date | None = None,
) -> SweepEvent | None:
    """First same-day hunt-window pierce of that day's Asia H/L or in-window EQH/EQL.

    Earlier session days cannot latch the result: both the range and the hunt
    window are filtered to ``session_day``.
    """
    day = _session_day(bars, session_day)
    if day is None:
        return None
    rng = asia_range(bars, settings, day)
    if rng is None:
        return None
    asia_high, asia_low, asia = rng
    eqh, eql = in_window_equal_levels(asia, settings)
    post = hunt_window_bars(bars, settings, day)
    if not post:
        return None

    for bar in post:
        high_asia = bar.high > asia_high + 1e-9
        low_asia = bar.low < asia_low - 1e-9
        high_eqh = eqh is not None and bar.high > eqh + 1e-9
        low_eql = eql is not None and bar.low < eql - 1e-9
        if high_asia or high_eqh:
            return SweepEvent(
                kind="high",
                ts=bar.ts,
                extreme=bar.high,
                asia_high=asia_high,
                asia_low=asia_low,
                source="asia" if high_asia else "eqh",
            )
        if low_asia or low_eql:
            return SweepEvent(
                kind="low",
                ts=bar.ts,
                extreme=bar.low,
                asia_high=asia_high,
                asia_low=asia_low,
                source="asia" if low_asia else "eql",
            )
    return None
