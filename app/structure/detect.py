"""Deterministic Setup A path: HTF → sweep → CHoCH/MSS → POI → one retrace."""

from __future__ import annotations

from app.config import Settings
from app.models import Bar, StructureResult
from app.structure.choch import find_choch
from app.structure.htf import htf_bias
from app.structure.poi import atr14, find_poi, find_retrace
from app.structure.sweep import find_sweep
from app.structure.swings import confirmed_swings


def detect(bars: list[Bar], settings: Settings) -> StructureResult | None:
    if len(bars) < 12:
        return None
    current = bars[-1]
    bias = htf_bias(bars, settings)
    sweep = find_sweep(bars, settings)
    if sweep is None:
        return None
    atr = atr14(bars)
    swings = confirmed_swings(bars, settings.swing_left, settings.swing_right)
    choch = find_choch(bars, sweep, swings=swings, atr=atr)
    if choch is None:
        return None
    poi = find_poi(bars, sweep, choch)
    if poi is None:
        return None
    retrace = find_retrace(bars, poi)
    if retrace is None:
        return None
    if retrace.ts != current.ts:
        return None

    side = "short" if sweep.kind == "high" else "long"
    with_trend = (side == "short" and bias == "bearish") or (side == "long" and bias == "bullish")
    sl = sweep.extreme + settings.sl_buffer if side == "short" else sweep.extreme - settings.sl_buffer
    choch_bar = next(b for b in bars if b.ts == choch.ts)
    displacement = (choch_bar.high - choch_bar.low) / atr if atr else 0.0
    setup_a = with_trend and poi.kind in {"fvg", "ob"}
    tags = ["sweep", "choch", "poi"]
    if choch.kind == "mss":
        tags.append("mss")
    if with_trend:
        tags.append("with_trend")
    if setup_a:
        tags.append("setup_a")
    if setup_a and displacement >= 1.5:
        grade = "A+"
    elif setup_a:
        grade = "A"
    else:
        grade = "B"
    return StructureResult(
        symbol=current.symbol,
        ts=retrace.ts,
        side=side,
        htf_bias=bias,
        with_trend=with_trend,
        sweep=sweep,
        choch=choch,
        poi=poi,
        retrace_bar_ts=retrace.ts,
        planned_entry=retrace.close,
        sl=round(sl, 5),
        tags=tags,
        grade=grade,
        displacement_atr=displacement,
        setup_a=setup_a,
    )
