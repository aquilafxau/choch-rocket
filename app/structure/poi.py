"""Displacement → FVG / order-block POI, then the first retrace."""

from __future__ import annotations

from app.models import Bar, ChochEvent, POIZone, SweepEvent


def atr14(bars: list[Bar]) -> float:
    if len(bars) < 2:
        return 0.0
    window = bars[-15:] if len(bars) >= 15 else bars
    trs: list[float] = []
    for i in range(1, len(window)):
        prev = window[i - 1]
        bar = window[i]
        tr = max(bar.high - bar.low, abs(bar.high - prev.close), abs(bar.low - prev.close))
        trs.append(tr)
    return sum(trs) / len(trs) if trs else 0.0


def find_poi(bars: list[Bar], sweep: SweepEvent, choch: ChochEvent) -> POIZone | None:
    choch_index = next((i for i, b in enumerate(bars) if b.ts == choch.ts), None)
    if choch_index is None:
        return None
    short = sweep.kind == "high"
    # FVG confirms on a candle *after* the shift. Do not treat the CHoCH bar as the POI tap.
    fvg = _first_fvg(bars, start=max(choch_index + 1, 2), short=short)
    if fvg:
        return fvg
    if choch_index >= len(bars) - 1:
        return None
    return _order_block(bars, choch_index, short=short)


def _first_fvg(bars: list[Bar], start: int, short: bool) -> POIZone | None:
    for i in range(start, len(bars)):
        if i < 2:
            continue
        a, c = bars[i - 2], bars[i]
        if short and a.low > c.high + 1e-9:
            return POIZone(
                kind="fvg",
                ts=c.ts,
                low=c.high,
                high=a.low,
                direction="bearish",
            )
        if not short and a.high < c.low - 1e-9:
            return POIZone(
                kind="fvg",
                ts=c.ts,
                low=a.high,
                high=c.low,
                direction="bullish",
            )
    return None


def _order_block(bars: list[Bar], choch_index: int, short: bool) -> POIZone | None:
    for j in range(choch_index - 1, -1, -1):
        bar = bars[j]
        bullish = bar.close > bar.open
        if short and bullish:
            return POIZone(
                kind="ob",
                ts=bar.ts,
                low=min(bar.open, bar.close),
                high=max(bar.high, bar.open, bar.close),
                direction="bearish",
            )
        if not short and not bullish:
            return POIZone(
                kind="ob",
                ts=bar.ts,
                low=min(bar.low, bar.open, bar.close),
                high=max(bar.open, bar.close),
                direction="bullish",
            )
    return None


def find_retrace(bars: list[Bar], poi: POIZone) -> Bar | None:
    after = False
    for bar in bars:
        if bar.ts == poi.ts:
            after = True
            continue
        if not after:
            continue
        if poi.direction == "bearish" and bar.high > poi.low + 1e-8:
            return bar
        if poi.direction == "bullish" and bar.low < poi.high - 1e-8:
            return bar
    return None
