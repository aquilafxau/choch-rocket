"""News calendar: stub JSON now, Forex Factory later — rails only call veto_reason().

Swap path (no gate rewrite):
1. Convert an FF export (or live client) into ``RedFolderEvent`` / ``DecisionDay``.
2. Return a ``NewsCalendar`` from ``calendar_provider(settings)``.
3. Set ``NEWS_SOURCE=forexfactory`` once ``ForexFactoryCalendar.fetch()`` is implemented.
   Until then, ``forexfactory`` reads the same JSON cache as the stub.

JSON shape (``data/news_stub.json``)::

    {
      "source": "stub",
      "red_folder": [
        {"ts": "2026-03-10T08:30:00-04:00", "name": "CPI", "currency": "USD", "impact": "red"}
      ],
      "decision_days": [
        {"date": "2026-03-18", "name": "FOMC", "tz": "America/New_York"},
        "2026-04-10"
      ]
    }

Red-folder veto: event time ± ``red_folder_buffer_min`` (default 30).
CPI/FOMC decision-day veto: bar's civil date in the event timezone (default America/New_York).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.timeutil import NY, to_tz


class RedFolderEvent(BaseModel):
    ts: datetime
    name: str = "red"
    currency: str | None = None
    impact: str = "red"


class DecisionDay(BaseModel):
    date: date
    name: str = "cpi_fomc"
    tz: str = "America/New_York"


class CalendarProvider(Protocol):
    """Rails depend on this, not on how events were fetched."""

    source: str

    def veto_reason(self, ts: datetime, buffer_min: int = 30) -> str | None: ...


class NewsCalendar(BaseModel):
    red_folder: list[RedFolderEvent] = Field(default_factory=list)
    decision_days: list[DecisionDay] = Field(default_factory=list)
    source: str = "stub"

    def is_decision_day(self, ts: datetime) -> bool:
        for day in self.decision_days:
            try:
                zone = ZoneInfo(day.tz)
            except Exception:
                zone = NY
            if to_tz(ts, zone).date() == day.date:
                return True
        return False

    def is_red_folder_window(self, ts: datetime, buffer_min: int = 30) -> bool:
        window = timedelta(minutes=buffer_min)
        for event in self.red_folder:
            event_ts = event.ts if event.ts.tzinfo else event.ts.replace(tzinfo=NY)
            aware = ts if ts.tzinfo else ts.replace(tzinfo=NY)
            if abs(aware - event_ts) <= window:
                return True
        return False

    def veto_reason(self, ts: datetime, buffer_min: int = 30) -> str | None:
        if self.is_decision_day(ts):
            return "cpi_fomc"
        if self.is_red_folder_window(ts, buffer_min):
            return "red_folder"
        return None


def load_calendar(path: str | Path) -> NewsCalendar:
    file = Path(path)
    if not file.exists():
        return NewsCalendar()
    raw = json.loads(file.read_text())
    return _from_mapping(raw, source=str(raw.get("source") or "stub"))


def _from_mapping(raw: dict, source: str) -> NewsCalendar:
    events: list[RedFolderEvent] = []
    for item in raw.get("red_folder", []):
        events.append(
            RedFolderEvent(
                ts=datetime.fromisoformat(item["ts"]),
                name=item.get("name", "red"),
                currency=item.get("currency"),
                impact=item.get("impact", "red"),
            )
        )
    days: list[DecisionDay] = []
    for item in raw.get("decision_days", []):
        if isinstance(item, str):
            days.append(DecisionDay(date=date.fromisoformat(item)))
            continue
        days.append(
            DecisionDay(
                date=date.fromisoformat(item["date"]),
                name=item.get("name", "cpi_fomc"),
                tz=item.get("tz", "America/New_York"),
            )
        )
    return NewsCalendar(red_folder=events, decision_days=days, source=source)


def is_decision_day(ts: datetime, calendar: NewsCalendar) -> bool:
    return calendar.is_decision_day(ts)


def is_red_folder_window(ts: datetime, calendar: NewsCalendar, buffer_min: int) -> bool:
    return calendar.is_red_folder_window(ts, buffer_min)


class ForexFactoryCalendar:
    """P1 adapter slot for a real Forex Factory feed.

    Do not change ``app/rails/gate.py`` when wiring FF. Implement ``fetch()``
    (HTTP/CSV → ``NewsCalendar``) and select it with ``NEWS_SOURCE=forexfactory``.
    Until fetch exists, this reads the stub JSON cache so rails stay identical.
    """

    source = "forexfactory"

    @staticmethod
    def from_cache(path: str | Path) -> NewsCalendar:
        cal = load_calendar(path)
        cal.source = "forexfactory"
        return cal

    @staticmethod
    def fetch() -> NewsCalendar:
        raise NotImplementedError(
            "Live Forex Factory HTTP is not wired. Convert an FF export to "
            "data/news_stub.json (same schema) or implement ForexFactoryCalendar.fetch()."
        )


def calendar_provider(settings) -> NewsCalendar:
    source = (getattr(settings, "news_source", None) or "stub").strip().lower()
    path = getattr(settings, "news_stub_path", "data/news_stub.json")
    if source == "forexfactory":
        return ForexFactoryCalendar.from_cache(path)
    return load_calendar(path)
