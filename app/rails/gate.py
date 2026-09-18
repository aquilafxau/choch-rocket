"""Hard rails: pair, London, with-trend, news stub, stop-after-2L, HALF sizing."""

from __future__ import annotations

from app.config import Settings
from app.db import Store
from app.models import StructureResult
from app.rails.calendar import is_decision_day, is_red_folder_window, load_calendar
from app.timeutil import aest_date, on_clock, to_aest


def session_name(ts, settings: Settings) -> str | None:
    start, end = settings.london_window
    if on_clock(ts, start, end):
        return "london"
    if settings.ny_session_enabled:
        ny_start, ny_end = (p.strip() for p in settings.session_ny.split("-"))
        from app.timeutil import parse_clock

        if on_clock(ts, parse_clock(ny_start), parse_clock(ny_end)):
            return "ny"
    return None


def gate(
    structure: StructureResult,
    settings: Settings,
    store: Store,
    calendar=None,
) -> tuple[str, str | None, str | None, float]:
    """Return decision, veto_reason, session, planned_risk_usd."""
    calendar = calendar if calendar is not None else load_calendar(settings.news_stub_path)
    ts = structure.ts
    session = session_name(ts, settings)

    if not settings.allowed_symbol(structure.symbol):
        return "VETO", "pair_not_allowed", session, 0.0
    if session is None:
        return "VETO", "outside_session", session, 0.0
    if structure.htf_bias == "neutral":
        return "VETO", "htf_unclear", session, 0.0
    if not structure.with_trend:
        return "VETO", "against_trend", session, 0.0
    if is_decision_day(ts, calendar):
        return "VETO", "cpi_fomc", session, 0.0
    if is_red_folder_window(ts, calendar, settings.red_folder_buffer_min):
        return "VETO", "red_folder", session, 0.0

    losses = store.losses_on_date(aest_date(ts))
    if losses >= settings.stop_after_losses:
        return "VETO", "day_stop", session, 0.0

    risk = settings.risk_usd
    decision = "GO"
    weekday = to_aest(ts).weekday()
    midweek = weekday in (2, 3)
    if settings.two_year_flat:
        if structure.grade != "A+":
            return "VETO", "two_year_flat", session, 0.0
        decision = "HALF"
        risk = settings.risk_usd / 2.0
    elif midweek and structure.grade != "A+":
        decision = "HALF"
        risk = settings.risk_usd / 2.0

    return decision, None, session, risk
