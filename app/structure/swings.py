"""Confirmed swing highs/lows (no unconfirmed right-side bars)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models import Bar


class Swing(BaseModel):
    kind: str
    index: int
    ts: datetime
    price: float


def confirmed_swings(bars: list[Bar], left: int = 2, right: int = 2) -> list[Swing]:
    out: list[Swing] = []
    n = len(bars)
    for i in range(left, n - right):
        high = bars[i].high
        low = bars[i].low
        left_range = range(i - left, i)
        right_range = range(i + 1, i + right + 1)
        if all(high > bars[j].high for j in left_range) and all(high > bars[j].high for j in right_range):
            out.append(Swing(kind="high", index=i, ts=bars[i].ts, price=high))
        if all(low < bars[j].low for j in left_range) and all(low < bars[j].low for j in right_range):
            out.append(Swing(kind="low", index=i, ts=bars[i].ts, price=low))
    return out
