from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from app.config import Settings
from app.db import Store
from app.ingest.synthetic import build_setup_a_bars
from app.models import Bar, StructureResult, SweepEvent, ChochEvent, POIZone
from app.pipeline import Pipeline
from app.timeutil import AEST


@contextmanager
def asgi_client(app: FastAPI) -> Iterator[httpx.Client]:
    """httpx ASGI client — avoids Starlette TestClient's httpx/httpx2 deprecation."""
    transport = httpx.ASGITransport(app=app)
    with httpx.Client(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    return Settings(db_path=str(tmp_path / "choch.db"), news_stub_path=str(tmp_path / "news.json"))


@pytest.fixture
def pipeline(tmp_settings: Settings) -> Pipeline:
    return Pipeline(Store(tmp_settings.db_path), tmp_settings)


@pytest.fixture
def setup_a_bars() -> list[Bar]:
    return build_setup_a_bars()


def structure_stub(
    *,
    ts: datetime | None = None,
    symbol: str = "EURUSD",
    side: str = "short",
    htf_bias: str = "bearish",
    with_trend: bool = True,
    grade: str = "A",
    tags: list[str] | None = None,
) -> StructureResult:
    ts = ts or datetime(2026, 3, 10, 16, 45, tzinfo=AEST)
    sweep = SweepEvent(kind="high", ts=ts - timedelta(minutes=45), extreme=1.08640, asia_high=1.08580, asia_low=1.08280)
    choch = ChochEvent(ts=ts - timedelta(minutes=30), level=1.08280, kind="mss")
    poi = POIZone(kind="fvg", ts=ts - timedelta(minutes=15), low=1.08220, high=1.08510, direction="bearish")
    return StructureResult(
        symbol=symbol,
        ts=ts,
        side=side,  # type: ignore[arg-type]
        htf_bias=htf_bias,  # type: ignore[arg-type]
        with_trend=with_trend,
        sweep=sweep,
        choch=choch,
        poi=poi,
        retrace_bar_ts=ts,
        planned_entry=1.08310,
        sl=1.08660,
        tags=tags or ["with_trend", "sweep", "choch", "poi", "setup_a"],
        grade=grade,
        displacement_atr=2.4,
        setup_a=with_trend,
    )
