"""NewsCalendar: red-folder ±30m and CPI/FOMC decision-day vetoes."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from app.config import Settings
from app.db import Store
from app.ingest.synthetic import build_setup_a_bars
from app.pipeline import Pipeline
from app.rails.calendar import (
    DecisionDay,
    ForexFactoryCalendar,
    NewsCalendar,
    RedFolderEvent,
    calendar_provider,
)
from app.recommend.emit import emit
from app.timeutil import AEST, NY
from tests.conftest import structure_stub


def test_red_folder_veto_within_30m(tmp_settings: Settings):
    store = Store(tmp_settings.db_path)
    ts = datetime(2026, 3, 10, 16, 45, tzinfo=AEST)
    cal = NewsCalendar(
        red_folder=[RedFolderEvent(ts=ts - timedelta(minutes=20), name="USD CPI", currency="USD")],
        source="stub",
    )
    signal = emit(structure_stub(ts=ts), tmp_settings, store, calendar=cal)
    assert signal.decision == "VETO"
    assert signal.veto_reason == "red_folder"
    assert store.list_trades() == []


def test_red_folder_allows_outside_buffer(tmp_settings: Settings):
    store = Store(tmp_settings.db_path)
    ts = datetime(2026, 3, 10, 16, 45, tzinfo=AEST)
    cal = NewsCalendar(
        red_folder=[RedFolderEvent(ts=ts - timedelta(minutes=90), name="USD CPI")],
    )
    signal = emit(structure_stub(ts=ts), tmp_settings, store, calendar=cal)
    assert signal.decision in {"GO", "HALF"}
    assert signal.veto_reason is None


def test_red_folder_veto_on_replay(tmp_path: Path):
    news = tmp_path / "news.json"
    news.write_text(
        """
        {
          "source": "stub",
          "red_folder": [
            {"ts": "2026-03-10T16:45:00+10:00", "name": "NFP", "currency": "USD", "impact": "red"}
          ],
          "decision_days": []
        }
        """
    )
    settings = Settings(db_path=str(tmp_path / "choch.db"), news_stub_path=str(news))
    pipeline = Pipeline(Store(settings.db_path), settings)
    signals = pipeline.replay(build_setup_a_bars())
    assert any(s.decision == "VETO" and s.veto_reason == "red_folder" for s in signals)
    assert pipeline.store.list_trades() == []


def test_cpi_fomc_decision_day_veto(tmp_settings: Settings):
    store = Store(tmp_settings.db_path)
    cal = NewsCalendar(
        decision_days=[DecisionDay(date=date(2026, 3, 10), name="FOMC", tz="America/New_York")],
    )
    # 16:45 AEST 10 Mar = 01:45 EDT 10 Mar → US decision day.
    signal = emit(structure_stub(), tmp_settings, store, calendar=cal)
    assert signal.decision == "VETO"
    assert signal.veto_reason == "cpi_fomc"


def test_forexfactory_slot_uses_cache_not_http(tmp_path: Path):
    news = tmp_path / "news.json"
    news.write_text('{"source": "stub", "red_folder": [], "decision_days": []}')
    settings = Settings(
        db_path=str(tmp_path / "t.db"),
        news_stub_path=str(news),
        news_source="forexfactory",
    )
    cal = calendar_provider(settings)
    assert cal.source == "forexfactory"
    assert cal.veto_reason(datetime(2026, 3, 10, 16, 45, tzinfo=AEST)) is None
    with pytest.raises(NotImplementedError):
        ForexFactoryCalendar.fetch()


def test_decision_day_string_dates_in_json(tmp_path: Path):
    news = tmp_path / "news.json"
    news.write_text('{"decision_days": ["2026-03-10"], "red_folder": []}')
    settings = Settings(db_path=str(tmp_path / "t.db"), news_stub_path=str(news))
    cal = calendar_provider(settings)
    ts = datetime(2026, 3, 10, 10, 0, tzinfo=NY)
    assert cal.veto_reason(ts) == "cpi_fomc"
