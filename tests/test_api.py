import pytest

from app.config import Settings
from app.ingest.synthetic import build_setup_a_bars
from app.main import create_app
from app.pipeline import Pipeline
from tests.conftest import asgi_client


@pytest.mark.anyio
async def test_health_shadow_only(tmp_settings: Settings):
    async with asgi_client(create_app(tmp_settings)) as client:
        body = (await client.get("/health")).json()
        assert body["ok"] is True
        assert body["shadow_only"] is True
        assert body["pairs"] == ["EURUSD", "AUDUSD"]
        assert "16:00" in body["session_london"]


@pytest.mark.anyio
async def test_dashboard_and_stats_after_replay(tmp_settings: Settings):
    app = create_app(tmp_settings)
    Pipeline(app.state.store, tmp_settings).replay(build_setup_a_bars())
    async with asgi_client(app) as client:
        html = (await client.get("/")).text
        assert "SHADOW ONLY" in html
        stats = (await client.get("/stats")).json()
        assert stats["overall"]["n"] == 1
        assert stats["overall"]["wr"] == 1.0
        assert "stop_after_2l" in stats["counterfactuals"]
        assert "a_plus_only" in stats["counterfactuals"]
        assert "london_only" in stats["counterfactuals"]
        signals = (await client.get("/signals")).json()
        assert signals[0]["decision"] in {"GO", "HALF"}


@pytest.mark.anyio
async def test_tv_hook_accepts_bar(tmp_settings: Settings):
    async with asgi_client(create_app(tmp_settings)) as client:
        res = await client.post(
            "/hooks/tv",
            json={
                "symbol": "EURUSD",
                "timeframe": "M15",
                "time": "2026-03-10T07:00:00+10:00",
                "open": 1.08500,
                "high": 1.08520,
                "low": 1.08480,
                "close": 1.08490,
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["accepted"] is True
        assert body["symbol"] == "EURUSD"
