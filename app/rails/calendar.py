"""Stub news calendar. Empty by default; load JSON if present."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel

from app.timeutil import aest_date, to_aest


class RedFolderEvent(BaseModel):
    ts: datetime
    name: str = "red"


class NewsCalendar(BaseModel):
    red_folder: list[RedFolderEvent] = []
    decision_days: list[str] = []


def load_calendar(path: str | Path) -> NewsCalendar:
    file = Path(path)
    if not file.exists():
        return NewsCalendar()
    raw = json.loads(file.read_text())
    events = []
    for item in raw.get("red_folder", []):
        events.append(RedFolderEvent(ts=datetime.fromisoformat(item["ts"]), name=item.get("name", "red")))
    return NewsCalendar(red_folder=events, decision_days=list(raw.get("decision_days", [])))


def is_decision_day(ts: datetime, calendar: NewsCalendar) -> bool:
    return aest_date(ts).isoformat() in set(calendar.decision_days)


def is_red_folder_window(ts: datetime, calendar: NewsCalendar, buffer_min: int) -> bool:
    local = to_aest(ts)
    window = timedelta(minutes=buffer_min)
    for event in calendar.red_folder:
        event_ts = to_aest(event.ts)
        if abs(local - event_ts) <= window:
            return True
    return False
