"""H1/H4 resampling and directional bias."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from app.config import Settings
from app.models import Bar, Bias
from app.timeutil import to_aest


def floor_bucket(ts: datetime, hours: int) -> datetime:
    local = to_aest(ts)
    hour = (local.hour // hours) * hours
    return local.replace(hour=hour, minute=0, second=0, microsecond=0)


def resample(bars: list[Bar], hours: int) -> list[Bar]:
    buckets: dict[datetime, list[Bar]] = defaultdict(list)
    for bar in bars:
        buckets[floor_bucket(bar.ts, hours)].append(bar)

    out: list[Bar] = []
    for start, group in sorted(buckets.items()):
        group = sorted(group, key=lambda b: b.ts)
        bucket_end = start + timedelta(hours=hours)
        last_ts = to_aest(group[-1].ts)
        complete = last_ts >= bucket_end - timedelta(minutes=15)
        if not complete:
            continue
        out.append(
            Bar(
                ts=start,
                open=group[0].open,
                high=max(b.high for b in group),
                low=min(b.low for b in group),
                close=group[-1].close,
                volume=sum(b.volume for b in group),
                symbol=group[0].symbol,
                timeframe=f"H{hours}",
            )
        )
    return out


def _signed_change(series: list[Bar], lookback: int) -> float | None:
    if len(series) < min(3, lookback):
        return None
    window = series[-lookback:] if len(series) >= lookback else series
    if window[0].close == 0:
        return None
    return window[-1].close / window[0].close - 1.0


def htf_bias(bars: list[Bar], settings: Settings) -> Bias:
    """Directional bias from completed H4, falling back to a wider H1 window.

    Uses a 4-candle H4 lookback so a London range does not wipe a clear overnight trend.
    """
    h4 = resample(bars, 4)
    change = _signed_change(h4, 4)
    if change is not None:
        if change <= -settings.htf_min_move:
            return "bearish"
        if change >= settings.htf_min_move:
            return "bullish"
    h1 = resample(bars, 1)
    change = _signed_change(h1, 8)
    if change is not None:
        if change <= -settings.htf_min_move:
            return "bearish"
        if change >= settings.htf_min_move:
            return "bullish"
    return "neutral"
