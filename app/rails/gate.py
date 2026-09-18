"""Hard rails: pair, London|NY sessions, with-trend, news, stop-after-2L, HALF sizing."""

from __future__ import annotations

from app.config import Settings
from app.db import Store
from app.models import StructureResult
from app.rails.calendar import calendar_provider
from app.rails.sessions import session_name
from app.timeutil import aest_date, to_aest


def gate(
    structure: StructureResult,
    settings: Settings,
    store: Store,
    calendar=None,
) -> tuple[str, str | None, str | None, float]:
    """Return decision, veto_reason, session, planned_risk_usd."""
    calendar = calendar if calendar is not None else calendar_provider(settings)
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
    news_veto = calendar.veto_reason(ts, settings.red_folder_buffer_min)
    if news_veto:
        return "VETO", news_veto, session, 0.0

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
