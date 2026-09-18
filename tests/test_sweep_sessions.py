"""Asia range / sweep must be per AEST session day — not latched to day 1."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.config import Settings
from app.ingest.synthetic import build_multi_day_setup_a_bars, build_setup_a_bars
from app.models import Bar
from app.pipeline import Pipeline
from app.structure.sweep import asia_range, find_sweep
from app.timeutil import AEST, aest_date


def _bar(ts: datetime, o: float, h: float, l: float, c: float) -> Bar:
    return Bar(ts=ts, open=o, high=h, low=l, close=c, volume=100, symbol="EURUSD")


def _asia_session(day: datetime, high: float, low: float) -> list[Bar]:
    """Four quiet Asia M15 bars on ``day`` with a known H/L."""
    start = day.replace(hour=7, minute=0, second=0, microsecond=0)
    mid = (high + low) / 2
    bars = []
    for i in range(4):
        ts = start + timedelta(minutes=15 * i)
        # First bar prints the session high; last bar prints the session low.
        h = high if i == 0 else mid + 0.00020
        l = low if i == 3 else mid - 0.00020
        bars.append(_bar(ts, mid, h, l, mid))
    return bars


def _london_pierce(day: datetime, extreme: float, *, kind: str = "high") -> Bar:
    ts = day.replace(hour=16, minute=0, second=0, microsecond=0)
    if kind == "high":
        return _bar(ts, extreme - 0.00020, extreme, extreme - 0.00040, extreme - 0.00010)
    return _bar(ts, extreme + 0.00020, extreme + 0.00040, extreme, extreme + 0.00010)


def _two_day_mega_range_fixture() -> list[Bar]:
    """Day 1 Asia high 1.100 / Day 2 Asia high 1.082; each London pierces only its own day.

    A global mega-range would set asia_high=1.100 and miss the day-2 pierce at 1.083.
    """
    day1 = datetime(2026, 3, 10, tzinfo=AEST)
    day2 = datetime(2026, 3, 11, tzinfo=AEST)
    return [
        *_asia_session(day1, high=1.10000, low=1.09200),
        _london_pierce(day1, 1.10100, kind="high"),
        *_asia_session(day2, high=1.08200, low=1.07800),
        _london_pierce(day2, 1.08300, kind="high"),
    ]


def test_asia_range_is_per_session_day_not_global_mega_range():
    settings = Settings()
    bars = _two_day_mega_range_fixture()
    day1 = aest_date(bars[0].ts)
    day2 = aest_date(bars[-1].ts)

    rng_default = asia_range(bars, settings)
    assert rng_default is not None
    asia_high, asia_low, asia = rng_default
    assert all(aest_date(b.ts) == day2 for b in asia)
    assert abs(asia_high - 1.08200) < 1e-9
    assert abs(asia_low - 1.07800) < 1e-9

    rng_day1 = asia_range(bars, settings, session_day=day1)
    assert rng_day1 is not None
    assert abs(rng_day1[0] - 1.10000) < 1e-9
    assert abs(rng_day1[1] - 1.09200) < 1e-9

    # Mega-range (the bug) would have been max/min across both Asia sessions.
    assert asia_high < 1.10000 - 1e-9


def test_find_sweep_does_not_latch_on_first_day_pierce():
    settings = Settings()
    bars = _two_day_mega_range_fixture()
    day1 = aest_date(bars[0].ts)
    day2 = aest_date(bars[-1].ts)

    sweep_all = find_sweep(bars, settings)
    assert sweep_all is not None
    assert aest_date(sweep_all.ts) == day2
    assert sweep_all.kind == "high"
    assert abs(sweep_all.extreme - 1.08300) < 1e-9
    assert abs(sweep_all.asia_high - 1.08200) < 1e-9

    sweep_day1 = find_sweep(bars, settings, session_day=day1)
    assert sweep_day1 is not None
    assert aest_date(sweep_day1.ts) == day1
    assert abs(sweep_day1.extreme - 1.10100) < 1e-9
    assert abs(sweep_day1.asia_high - 1.10000) < 1e-9

    # Prefix through day 1 still finds that day's sweep (no lookahead, no regression).
    day1_end = next(i for i, b in enumerate(bars) if aest_date(b.ts) == day1 and b.ts.hour == 16)
    sweep_prefix = find_sweep(bars[: day1_end + 1], settings)
    assert sweep_prefix == sweep_day1


def test_find_sweep_fires_once_per_session_day_on_growing_history():
    settings = Settings()
    bars = build_multi_day_setup_a_bars(days=3)
    first_by_day: dict = {}
    for i in range(len(bars)):
        hist = bars[: i + 1]
        sweep = find_sweep(hist, settings)
        if sweep is None:
            continue
        day = aest_date(sweep.ts)
        if day not in first_by_day:
            first_by_day[day] = sweep.ts
        else:
            assert first_by_day[day] == sweep.ts

    assert len(first_by_day) == 3
    # Full-history call must be the last session day, not day 1.
    final = find_sweep(bars, settings)
    assert final is not None
    assert aest_date(final.ts) == max(first_by_day)


def test_single_day_setup_a_sweep_unchanged():
    settings = Settings()
    bars = build_setup_a_bars()
    london = [b for b in bars if b.ts <= datetime(2026, 3, 10, 16, 45, tzinfo=AEST)]
    sweep = find_sweep(london, settings)
    assert sweep is not None
    assert sweep.kind == "high"
    assert aest_date(sweep.ts) == datetime(2026, 3, 10, tzinfo=AEST).date()


def test_multi_day_replay_emits_multiple_signals(pipeline: Pipeline):
    bars = build_multi_day_setup_a_bars(days=3)
    signals = pipeline.replay(bars)
    days = {aest_date(s.ts) for s in signals}
    assert len(signals) >= 2, f"latch regression: expected signals across days, got {signals!r}"
    assert len(days) >= 2, f"signals must land on more than one AEST day, got {days} from {signals!r}"
    assert all("sweep" in s.tags for s in signals)
