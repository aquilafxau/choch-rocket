"""P1: NY session window + flatten at 12:00 America/New_York."""

from __future__ import annotations

from datetime import datetime

from app.config import Settings
from app.db import Store
from app.ingest.synthetic import build_ny_setup_a_bars
from app.pipeline import Pipeline
from app.recommend.emit import emit
from app.timeutil import NY
from tests.conftest import structure_stub


def test_ny_go_path_fixture(tmp_path):
    settings = Settings(db_path=str(tmp_path / "choch.db"), ny_session_enabled=True)
    store = Store(settings.db_path)
    pipeline = Pipeline(store, settings)
    bars = build_ny_setup_a_bars()
    signals = pipeline.replay(bars)
    actionable = [s for s in signals if s.decision in {"GO", "HALF"}]
    assert actionable, f"expected NY GO/HALF, got {signals!r}"
    signal = actionable[0]
    assert signal.session == "ny"
    assert "ny" in signal.tags
    assert signal.side == "short"
    for tag in ("with_trend", "sweep", "choch", "poi", "setup_a"):
        assert tag in signal.tags
    trades = [t for t in store.list_trades() if t.status == "closed"]
    assert len(trades) == 1
    trade = trades[0]
    assert trade.session == "ny"
    assert trade.exit_reason in {"sl", "be", "session_end"}
    assert trade.r_multiple is not None
    if trade.exit_reason == "session_end":
        assert trade.exit_ts is not None
        assert trade.exit_ts.astimezone(NY).hour == 12
        assert trade.exit_ts.astimezone(NY).minute == 0


def test_ny_outside_window_veto(tmp_settings: Settings):
    settings = tmp_settings.model_copy(update={"ny_session_enabled": True})
    store = Store(settings.db_path)
    ts = datetime(2026, 3, 10, 14, 15, tzinfo=NY)
    signal = emit(structure_stub(ts=ts), settings, store)
    assert signal.decision == "VETO"
    assert signal.veto_reason == "outside_session"
    assert store.list_trades() == []


def test_ny_disabled_is_outside_session(tmp_settings: Settings):
    ts = datetime(2026, 3, 10, 9, 45, tzinfo=NY)
    signal = emit(structure_stub(ts=ts), tmp_settings, Store(tmp_settings.db_path))
    assert tmp_settings.ny_session_enabled is False
    assert signal.decision == "VETO"
    assert signal.veto_reason == "outside_session"


def test_london_still_goes_when_ny_enabled(tmp_settings: Settings):
    settings = tmp_settings.model_copy(update={"ny_session_enabled": True})
    store = Store(settings.db_path)
    signal = emit(structure_stub(), settings, store)
    assert signal.decision in {"GO", "HALF"}
    assert signal.session == "london"
    assert "london" in signal.tags
