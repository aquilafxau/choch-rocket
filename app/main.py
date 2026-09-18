"""FastAPI entry: webhook ingest, stats, health. Shadow-only — no order routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import Settings, get_settings
from app.db import Store
from app.ingest.csv_loader import bar_from_hook
from app.models import Signal, TvHookPayload
from app.pipeline import Pipeline
from app.stats.compute import summarize
from app.stats.html import render_dashboard


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    store = Store(settings.db_path)
    pipeline = Pipeline(store, settings)
    app = FastAPI(
        title="Choch Rocket",
        description="Protrend M15 GO/HALF/VETO recommender. Shadow sim only — no live orders.",
        version="0.1.0",
    )
    app.state.settings = settings
    app.state.store = store
    app.state.pipeline = pipeline

    @app.get("/health")
    def health(request: Request) -> dict:
        cfg: Settings = request.app.state.settings
        return {
            "ok": True,
            "shadow_only": cfg.shadow_only,
            "pairs": list(cfg.pairs),
            "session_london": cfg.session_london,
        }

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> str:
        db: Store = request.app.state.store
        return render_dashboard(summarize(db.list_trades()), db.list_signals(), db.list_trades())

    @app.get("/stats")
    def stats(request: Request) -> dict:
        db: Store = request.app.state.store
        payload = summarize(db.list_trades())
        signals = db.list_signals()
        payload["signals"] = {
            "n": len(signals),
            "go": sum(1 for s in signals if s.decision == "GO"),
            "half": sum(1 for s in signals if s.decision == "HALF"),
            "veto": sum(1 for s in signals if s.decision == "VETO"),
        }
        return payload

    @app.get("/signals")
    def signals(request: Request) -> list[dict]:
        db: Store = request.app.state.store
        return [_signal_json(s) for s in db.list_signals()]

    @app.post("/hooks/tv")
    def tv_hook(payload: TvHookPayload, request: Request) -> JSONResponse:
        pipe: Pipeline = request.app.state.pipeline
        bar = bar_from_hook(payload)
        signal = pipe.on_bar(bar)
        body = {
            "accepted": True,
            "symbol": bar.symbol,
            "ts": bar.ts.isoformat(),
            "signal": _signal_json(signal) if signal else None,
        }
        return JSONResponse(body)

    @app.post("/replay")
    def replay_not_for_orders() -> None:
        raise HTTPException(
            status_code=400,
            detail="Use scripts/replay_day.py for CSV replay. No order endpoint exists.",
        )

    return app


def _signal_json(signal: Signal | None) -> dict | None:
    if signal is None:
        return None
    return signal.model_dump(mode="json")


app = create_app()
