"""Synthetic M15 path that prints Setup A (sweep → CHoCH → FVG → one retrace)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from app.models import Bar
from app.timeutil import AEST

Trend = Literal["bullish", "bearish"]
Side = Literal["long", "short"]


def _bar(ts: datetime, o: float, h: float, l: float, c: float, symbol: str) -> Bar:
    high = max(h, o, c)
    low = min(l, o, c)
    return Bar(ts=ts, open=round(o, 5), high=round(high, 5), low=round(low, 5), close=round(c, 5), volume=100, symbol=symbol)


def _iter_m15(start: datetime, end: datetime):
    ts = start
    while ts < end:
        yield ts
        ts += timedelta(minutes=15)


def interpolate(start: datetime, end: datetime, start_px: float, end_px: float, symbol: str, wick: float = 0.00006) -> dict[datetime, Bar]:
    stamps = list(_iter_m15(start, end))
    n = max(len(stamps), 1)
    out: dict[datetime, Bar] = {}
    for i, ts in enumerate(stamps):
        o = start_px + (end_px - start_px) * i / n
        c = start_px + (end_px - start_px) * (i + 1) / n
        out[ts] = _bar(ts, o, max(o, c) + wick, min(o, c) - wick, c, symbol)
    return out


def build_setup_a_bars(
    *,
    symbol: str = "EURUSD",
    day: datetime | None = None,
    htf: Trend = "bearish",
    setup_side: Side = "short",
    sweep_hour: int = 16,
) -> list[Bar]:
    """Build a full AEST day of M15 bars with a completed Setup A sequence at sweep_hour."""
    day = day or datetime(2026, 3, 10, tzinfo=AEST)
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=21, minutes=15)

    if htf == "bearish":
        overnight = interpolate(start, start.replace(hour=8), 1.09200, 1.08520, symbol)
    else:
        overnight = interpolate(start, start.replace(hour=8), 1.07000, 1.08520, symbol)

    range_start = start.replace(hour=8)
    sweep_ts = start.replace(hour=sweep_hour, minute=0)
    # Quiet Asia/pre-sweep range with a defined high/low.
    # Gentle continuation through Asia so the last completed H4s still agree with HTF.
    asia_end_px = 1.08350 if htf == "bearish" else 1.08640
    quiet = interpolate(range_start, sweep_ts, 1.08520, asia_end_px, symbol, wick=0.00010)

    bars = {**overnight, **quiet}

    # Carve a late swing against the setup so CHoCH has a level to break.
    swing_low_ts = sweep_ts - timedelta(minutes=30)
    swing_pre = sweep_ts - timedelta(minutes=60)
    if swing_pre in bars:
        bars[swing_pre] = _bar(swing_pre, 1.08460, 1.08500, 1.08380, 1.08420, symbol)
    if swing_pre + timedelta(minutes=15) in bars:
        ts = swing_pre + timedelta(minutes=15)
        bars[ts] = _bar(ts, 1.08420, 1.08470, 1.08360, 1.08390, symbol)
    bars[swing_low_ts] = _bar(swing_low_ts, 1.08390, 1.08410, 1.08280, 1.08320, symbol)
    swing_post = sweep_ts - timedelta(minutes=15)
    bars[swing_post] = _bar(swing_post, 1.08320, 1.08460, 1.08310, 1.08440, symbol)

    asia_high = max(b.high for ts, b in bars.items() if 7 <= ts.hour < sweep_hour)
    if setup_side == "short":
        sweep = _bar(sweep_ts, 1.08450, max(asia_high + 0.00045, 1.08620), 1.08430, 1.08510, symbol)
        choch_ts = sweep_ts + timedelta(minutes=15)
        choch = _bar(choch_ts, 1.08510, 1.08520, 1.08190, 1.08210, symbol)
        fvg_ts = sweep_ts + timedelta(minutes=30)
        fvg = _bar(fvg_ts, 1.08210, 1.08220, 1.08170, 1.08190, symbol)
        retrace_ts = sweep_ts + timedelta(minutes=45)
        retrace = _bar(retrace_ts, 1.08190, 1.08340, 1.08180, 1.08310, symbol)
        fill_ts = sweep_ts + timedelta(hours=1)
        # Fill next-bar open, then trend in favor through +1R and hold to 21:00.
        fill = _bar(fill_ts, 1.08300, 1.08330, 1.08140, 1.08160, symbol)
        bars[sweep_ts] = sweep
        bars[choch_ts] = choch
        bars[fvg_ts] = fvg
        bars[retrace_ts] = retrace
        bars[fill_ts] = fill
        runner = fill.close
        t = fill_ts + timedelta(minutes=15)
        flatten = start.replace(hour=21, minute=0)
        while t <= flatten:
            if t == fill_ts + timedelta(minutes=15):
                bars[t] = _bar(t, runner, runner + 0.00010, 1.07900, 1.07920, symbol)
                runner = 1.07920
            else:
                nxt = runner - 0.00008
                bars[t] = _bar(t, runner, runner + 0.00006, nxt - 0.00004, nxt, symbol)
                runner = nxt
            t += timedelta(minutes=15)
    else:
        # Long mirror: sweep Asia low, CHoCH up, bullish FVG, retrace, rally.
        asia_low = min(b.low for ts, b in bars.items() if 7 <= ts.hour < sweep_hour)
        sweep = _bar(sweep_ts, 1.08440, 1.08460, min(asia_low - 0.00045, 1.08220), 1.08380, symbol)
        choch_ts = sweep_ts + timedelta(minutes=15)
        choch = _bar(choch_ts, 1.08380, 1.08720, 1.08370, 1.08700, symbol)
        fvg_ts = sweep_ts + timedelta(minutes=30)
        fvg = _bar(fvg_ts, 1.08700, 1.08740, 1.08690, 1.08720, symbol)
        retrace_ts = sweep_ts + timedelta(minutes=45)
        retrace = _bar(retrace_ts, 1.08720, 1.08730, 1.08560, 1.08580, symbol)
        fill_ts = sweep_ts + timedelta(hours=1)
        fill = _bar(fill_ts, 1.08590, 1.08780, 1.08570, 1.08750, symbol)
        bars[sweep_ts] = sweep
        bars[choch_ts] = choch
        bars[fvg_ts] = fvg
        bars[retrace_ts] = retrace
        bars[fill_ts] = fill
        runner = fill.close
        t = fill_ts + timedelta(minutes=15)
        flatten = start.replace(hour=21, minute=0)
        while t <= flatten:
            if t == fill_ts + timedelta(minutes=15):
                bars[t] = _bar(t, runner, 1.09040, runner - 0.00010, 1.09020, symbol)
                runner = 1.09020
            else:
                nxt = runner + 0.00008
                bars[t] = _bar(t, runner, nxt + 0.00004, runner - 0.00006, nxt, symbol)
                runner = nxt
            t += timedelta(minutes=15)

    # Ensure every 15m slot exists through flatten.
    by_ts = dict(bars)
    for ts in _iter_m15(start, end):
        if ts not in by_ts:
            prev = by_ts[max(k for k in by_ts if k < ts)]
            by_ts[ts] = _bar(ts, prev.close, prev.close + 0.00005, prev.close - 0.00005, prev.close, symbol)
    return [by_ts[ts] for ts in sorted(by_ts)]
