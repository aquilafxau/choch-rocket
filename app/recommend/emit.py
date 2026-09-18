"""Emit GO / HALF / VETO JSON. Never sends broker orders."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.config import Settings
from app.db import Store
from app.models import Signal, StructureResult
from app.rails.gate import gate


def emit(structure: StructureResult, settings: Settings, store: Store, calendar=None) -> Signal:
    decision, veto_reason, session, risk = gate(structure, settings, store, calendar=calendar)
    return Signal(
        id=str(uuid.uuid4()),
        ts=structure.ts,
        symbol=structure.symbol,
        side=structure.side,
        grade=structure.grade,
        decision=decision,
        veto_reason=veto_reason,
        entry=None if decision == "VETO" else structure.planned_entry,
        sl=None if decision == "VETO" else structure.sl,
        tp=None,
        session=session or "none",
        tags=list(structure.tags),
        planned_risk_usd=None if decision == "VETO" else risk,
        signal_bar_ts=structure.retrace_bar_ts,
        sweep_extreme=structure.sweep.extreme,
        htf_bias=structure.htf_bias,
    )


def veto_only(
    *,
    ts: datetime,
    symbol: str,
    reason: str,
    tags: list[str] | None = None,
    side: str | None = None,
    grade: str | None = None,
    session: str | None = None,
    htf_bias: str | None = None,
) -> Signal:
    return Signal(
        id=str(uuid.uuid4()),
        ts=ts,
        symbol=symbol,
        side=side,  # type: ignore[arg-type]
        grade=grade,
        decision="VETO",
        veto_reason=reason,
        session=session or "none",
        tags=tags or [],
        signal_bar_ts=ts,
        htf_bias=htf_bias,
    )
