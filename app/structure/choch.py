"""CHoCH / MSS: shift back after the sweep."""

from __future__ import annotations

from app.models import Bar, ChochEvent, SweepEvent
from app.structure.swings import Swing, confirmed_swings


def find_choch(
    bars: list[Bar],
    sweep: SweepEvent,
    swings: list[Swing] | None = None,
    atr: float = 0.0,
) -> ChochEvent | None:
    swings = swings if swings is not None else confirmed_swings(bars)
    sweep_index = next((i for i, b in enumerate(bars) if b.ts == sweep.ts), None)
    if sweep_index is None:
        return None

    if sweep.kind == "high":
        lows = [s for s in swings if s.kind == "low" and s.ts <= sweep.ts]
        level = lows[-1].price if lows else sweep.asia_low
        for bar in bars[sweep_index + 1 :]:
            if bar.close < level:
                kind = "mss" if _displacement(bar, atr) else "choch"
                return ChochEvent(ts=bar.ts, level=level, kind=kind)
    else:
        highs = [s for s in swings if s.kind == "high" and s.ts <= sweep.ts]
        level = highs[-1].price if highs else sweep.asia_high
        for bar in bars[sweep_index + 1 :]:
            if bar.close > level:
                kind = "mss" if _displacement(bar, atr) else "choch"
                return ChochEvent(ts=bar.ts, level=level, kind=kind)
    return None


def _displacement(bar: Bar, atr: float) -> bool:
    rng = bar.high - bar.low
    body = abs(bar.close - bar.open)
    if atr <= 0:
        return body > 0 and rng > 0
    return rng >= 1.5 * atr and body >= 0.6 * rng
