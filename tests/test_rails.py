from datetime import datetime

from app.config import Settings
from app.db import Store
from app.recommend.emit import emit
from app.timeutil import AEST
from tests.conftest import structure_stub


def test_midweek_half_unless_a_plus(tmp_settings: Settings):
    store = Store(tmp_settings.db_path)
    wed = datetime(2026, 3, 11, 16, 45, tzinfo=AEST)
    signal = emit(structure_stub(ts=wed, grade="A"), tmp_settings, store)
    assert signal.decision == "HALF"
    assert signal.planned_risk_usd == 50.0
    plus = emit(structure_stub(ts=wed, grade="A+"), tmp_settings, store)
    assert plus.decision == "GO"
    assert plus.planned_risk_usd == 100.0
