from datetime import datetime

from app.config import Settings
from app.ingest.synthetic import build_setup_a_bars
from app.structure.detect import detect
from app.structure.htf import htf_bias
from app.structure.sweep import find_sweep
from app.timeutil import AEST


def test_fixture_has_bearish_bias_and_sweep():
    settings = Settings()
    bars = build_setup_a_bars()
    london = [b for b in bars if b.ts <= datetime(2026, 3, 10, 16, 45, tzinfo=AEST)]
    assert htf_bias(london, settings) == "bearish"
    sweep = find_sweep(london, settings)
    assert sweep is not None
    assert sweep.kind == "high"
    result = detect(london, settings)
    assert result is not None
    assert result.setup_a
    assert result.side == "short"
    assert result.with_trend
    assert "setup_a" in result.tags
