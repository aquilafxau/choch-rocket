"""Asia range / sweep must be per AEST session day — not latched to day 1."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.config import Settings
from app.db import Store
from app.ingest.synthetic import build_multi_day_setup_a_bars, build_setup_a_bars
from app.models import Bar
from app.pipeline import Pipeline
from app.structure.sweep import (
    asia_range,
    current_london_bars,
    find_sweep,
    hunt_window_bars,
    in_window_equal_levels,
    london_range,
    prior_asia_bars,
    session_window_bars,
)
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


def _eqh_asia(day: datetime, *, wick_high: float, eqh: float, floor: float) -> list[Bar]:
    """Asia path with one unique wick high plus two confirmed equal swing highs."""
    start = day.replace(hour=7, minute=0, second=0, microsecond=0)
    mid = (eqh + floor) / 2
    spec: list[tuple[float, float]] = [
        (wick_high, mid),  # unique Asia high (index 0 — not a confirmed swing)
        (mid + 0.00020, mid - 0.00020),
        (mid + 0.00015, mid - 0.00015),
        (eqh, floor + 0.00010),  # EQH 1
        (mid + 0.00018, mid - 0.00010),
        (mid + 0.00012, mid - 0.00012),
        (mid + 0.00014, mid - 0.00014),
        (eqh, floor + 0.00010),  # EQH 2
        (mid + 0.00016, mid - 0.00010),
        (mid + 0.00012, mid - 0.00012),
        (mid + 0.00010, floor),
        (mid + 0.00008, mid - 0.00010),
    ]
    out: list[Bar] = []
    for i, (h, l) in enumerate(spec):
        ts = start + timedelta(minutes=15 * i)
        out.append(_bar(ts, mid, h, l, mid))
    return out


def _rising_asia(day: datetime, start_px: float, end_high: float) -> list[Bar]:
    """Monotonic Asia highs — no EQH — with ``end_high`` as the session high."""
    start = day.replace(hour=7, minute=0, second=0, microsecond=0)
    n = 10
    out: list[Bar] = []
    for i in range(n):
        ts = start + timedelta(minutes=15 * i)
        h = start_px + (end_high - start_px) * (i + 1) / n
        o = h - 0.00020
        out.append(_bar(ts, o, h, o - 0.00010, o + 0.00005))
    return out


def test_session_window_helpers_never_cross_days():
    settings = Settings()
    bars = _two_day_mega_range_fixture()
    day1 = aest_date(bars[0].ts)
    day2 = aest_date(bars[-1].ts)
    start, end = settings.asia_window

    asia1 = session_window_bars(bars, day1, start, end)
    asia2 = prior_asia_bars(bars, settings, day2)
    hunt1 = hunt_window_bars(bars, settings, day1)
    hunt2 = hunt_window_bars(bars, settings, day2)

    assert asia1 and all(aest_date(b.ts) == day1 for b in asia1)
    assert asia2 and all(aest_date(b.ts) == day2 for b in asia2)
    assert hunt1 and all(aest_date(b.ts) == day1 and b.ts.hour >= 16 for b in hunt1)
    assert hunt2 and all(aest_date(b.ts) == day2 and b.ts.hour >= 16 for b in hunt2)
    assert {aest_date(b.ts) for b in prior_asia_bars(bars, settings)} == {day2}

    lon1 = current_london_bars(bars, settings, day1)
    lon2 = london_range(bars, settings)
    assert lon1 and all(aest_date(b.ts) == day1 for b in lon1)
    assert lon2 is not None
    lon2_high, lon2_low, lon2_bars = lon2
    assert all(aest_date(b.ts) == day2 for b in lon2_bars)
    assert abs(lon2_high - 1.08300) < 1e-9
    # Mega London range would include day-1 pierce at 1.10100.
    assert lon2_high < 1.10100 - 1e-9
    assert lon2_low <= lon2_high


def test_in_window_eqh_sweep_without_taking_asia_high():
    settings = Settings()
    day = datetime(2026, 3, 10, tzinfo=AEST)
    asia = _eqh_asia(day, wick_high=1.08600, eqh=1.08450, floor=1.08200)
    eqh, eql = in_window_equal_levels(asia, settings)
    assert eqh is not None
    assert abs(eqh - 1.08450) < 1e-9
    assert eql is None or eql >= 1.08200 - 1e-9

    # London takes EQH but stays below the unique Asia wick high.
    pierce = _london_pierce(day, 1.08480, kind="high")
    sweep = find_sweep([*asia, pierce], settings)
    assert sweep is not None
    assert sweep.kind == "high"
    assert sweep.source == "eqh"
    assert abs(sweep.extreme - 1.08480) < 1e-9
    assert abs(sweep.asia_high - 1.08600) < 1e-9


def test_eqh_from_prior_day_does_not_leak():
    settings = Settings()
    day1 = datetime(2026, 3, 10, tzinfo=AEST)
    day2 = datetime(2026, 3, 11, tzinfo=AEST)
    day1_asia = _eqh_asia(day1, wick_high=1.08600, eqh=1.08450, floor=1.08200)
    day1_pierce = _london_pierce(day1, 1.08480, kind="high")
    # Day 2 Asia high is *above* day-1 EQH; London prints 1.0850 — would sweep
    # leaked day-1 EQH (1.08450) but does not take day-2 Asia high (1.09000)
    # and day 2 has no EQH of its own.
    day2_asia = _rising_asia(day2, start_px=1.08100, end_high=1.09000)
    day2_london = _london_pierce(day2, 1.08500, kind="high")
    bars = [*day1_asia, day1_pierce, *day2_asia, day2_london]

    assert in_window_equal_levels(day2_asia, settings) == (None, None)
    leaked = find_sweep(bars, settings)
    assert leaked is None, f"day-1 EQH leaked into day 2: {leaked!r}"

    day1_sweep = find_sweep(bars, settings, session_day=aest_date(day1))
    assert day1_sweep is not None
    assert day1_sweep.source == "eqh"


def test_month_scale_replay_emits_plausible_london_setup_count(tmp_settings: Settings):
    """Aug-like ~21 London days must not collapse to ~1 signal/month."""
    bars = build_multi_day_setup_a_bars(days=21)
    store = Store(tmp_settings.db_path)
    signals = Pipeline(store, tmp_settings).replay(bars)
    days = {aest_date(s.ts) for s in signals}
    assert len(bars) > 1500
    assert len(signals) >= 15, f"expected a month of setups, got {len(signals)}: {signals!r}"
    assert len(days) >= 15
    assert all(s.decision in {"GO", "HALF"} for s in signals)


def test_in_window_eql_sweep_without_taking_asia_low():
    settings = Settings()
    day = datetime(2026, 3, 10, tzinfo=AEST)
    # Mirror of EQH: unique Asia wick low plus two equal swing lows.
    start = day.replace(hour=7, minute=0, second=0, microsecond=0)
    mid = 1.08400
    wick_low, eql, ceiling = 1.08100, 1.08250, 1.08500
    spec = [
        (mid, wick_low),
        (mid + 0.00020, mid - 0.00020),
        (mid + 0.00015, mid - 0.00015),
        (ceiling - 0.00010, eql),
        (mid + 0.00010, mid - 0.00010),
        (mid + 0.00012, mid - 0.00012),
        (mid + 0.00014, mid - 0.00014),
        (ceiling - 0.00010, eql),
        (mid + 0.00016, mid - 0.00010),
        (mid + 0.00012, mid - 0.00012),
        (ceiling, mid - 0.00010),
        (mid + 0.00008, mid - 0.00010),
    ]
    asia = [_bar(start + timedelta(minutes=15 * i), mid, h, l, mid) for i, (h, l) in enumerate(spec)]
    eqh, eq_low = in_window_equal_levels(asia, settings)
    assert eq_low is not None
    assert abs(eq_low - eql) < 1e-9

    pierce = _london_pierce(day, 1.08220, kind="low")
    sweep = find_sweep([*asia, pierce], settings)
    assert sweep is not None
    assert sweep.kind == "low"
    assert sweep.source == "eql"
    assert abs(sweep.extreme - 1.08220) < 1e-9
    assert abs(sweep.asia_low - wick_low) < 1e-9
    _ = eqh


def test_london_window_eqh_is_session_scoped():
    """EQH printed in current London (not Asia) still sweeps, and does not leak to day 2."""
    settings = Settings()
    day1 = datetime(2026, 3, 10, tzinfo=AEST)
    day2 = datetime(2026, 3, 11, tzinfo=AEST)
    asia1 = _rising_asia(day1, start_px=1.08100, end_high=1.09000)
    asia2 = _rising_asia(day2, start_px=1.08100, end_high=1.09000)

    def _london_eqh(day: datetime) -> list[Bar]:
        start = day.replace(hour=16, minute=0, second=0, microsecond=0)
        mid, eqh, floor = 1.08300, 1.08450, 1.08220
        spec = [
            (mid + 0.00010, mid - 0.00010),
            (mid + 0.00012, mid - 0.00012),
            (eqh, floor),
            (mid + 0.00014, mid - 0.00010),
            (mid + 0.00010, mid - 0.00010),
            (eqh, floor),
            (mid + 0.00012, mid - 0.00010),
            (mid + 0.00010, mid - 0.00010),
            (1.08480, mid - 0.00010),  # pierce EQH, stay below Asia 1.090
        ]
        return [_bar(start + timedelta(minutes=15 * i), mid, h, l, mid) for i, (h, l) in enumerate(spec)]

    lon1 = _london_eqh(day1)
    # Day 2 London never takes Asia or forms EQH — a leaked day-1 EQH at 1.08450
    # would fire on this 1.08500 print.
    lon2 = [_london_pierce(day2, 1.08500, kind="high")]
    bars = [*asia1, *lon1, *asia2, *lon2]

    sweep_day1 = find_sweep([*asia1, *lon1], settings)
    assert sweep_day1 is not None
    assert sweep_day1.source == "eqh"
    assert aest_date(sweep_day1.ts) == aest_date(day1)

    leaked = find_sweep(bars, settings)
    assert leaked is None, f"London EQH leaked across days: {leaked!r}"


def test_multi_day_against_trend_still_veto(tmp_settings: Settings):
    bars = build_multi_day_setup_a_bars(days=3, htf="bullish", setup_side="short")
    store = Store(tmp_settings.db_path)
    pipeline = Pipeline(store, tmp_settings)
    signals = pipeline.replay(bars)
    assert signals, "against-trend path should still emit VETO (visible, not silent)"
    assert all(s.decision == "VETO" for s in signals)
    assert all(s.veto_reason == "against_trend" for s in signals)
    assert store.list_trades() == []

