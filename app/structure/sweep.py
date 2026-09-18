"""Asia/session liquidity sweep. No sweep = no trade."""

from __future__ import annotations

from app.config import Settings
from app.models import Bar, SweepEvent
from app.timeutil import on_clock, to_aest


def asia_range(bars: list[Bar], settings: Settings) -> tuple[float, float, list[Bar]] | None:
    start, end = settings.asia_window
    asia = [b for b in bars if on_clock(b.ts, start, end)]
    if len(asia) < 4:
        return None
    return max(b.high for b in asia), min(b.low for b in asia), asia


def find_sweep(bars: list[Bar], settings: Settings) -> SweepEvent | None:
    rng = asia_range(bars, settings)
    if rng is None:
        return None
    asia_high, asia_low, _asia = rng
    _, asia_end = settings.asia_window
    post = [b for b in bars if to_aest(b.ts).timetz().replace(tzinfo=None) > asia_end]
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
