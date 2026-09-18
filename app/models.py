"""Typed models for bars, structure, signals, and shadow fills."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Decision = Literal["GO", "HALF", "VETO"]
Side = Literal["long", "short"]
Bias = Literal["bullish", "bearish", "neutral"]


class Bar(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    symbol: str = "EURUSD"
    timeframe: str = "M15"

    def model_post_init(self, __context: object) -> None:
        symbol = self.symbol.upper().replace("/", "")
        object.__setattr__(self, "symbol", symbol)
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError(f"Invalid OHLC at {self.ts}: {self.open, self.high, self.low, self.close}")


class SweepEvent(BaseModel):
    kind: Literal["high", "low"]
    ts: datetime
    extreme: float
    asia_high: float
    asia_low: float


class ChochEvent(BaseModel):
    ts: datetime
    level: float
    kind: Literal["choch", "mss"] = "choch"


class POIZone(BaseModel):
    kind: Literal["fvg", "ob"]
    ts: datetime
    low: float
    high: float
    direction: Literal["bullish", "bearish"]

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.ts.isoformat()}:{self.low:.5f}:{self.high:.5f}"


class StructureResult(BaseModel):
    symbol: str
    ts: datetime
    side: Side
    htf_bias: Bias
    with_trend: bool
    sweep: SweepEvent
    choch: ChochEvent
    poi: POIZone
    retrace_bar_ts: datetime
    planned_entry: float
    sl: float
    tags: list[str]
    grade: str
    displacement_atr: float
    setup_a: bool

    @property
    def poi_key(self) -> str:
        return f"{self.symbol}:{self.poi.key}"


class Signal(BaseModel):
    id: str
    ts: datetime
    symbol: str
    side: Side | None = None
    grade: str | None = None
    decision: Decision
    veto_reason: str | None = None
    entry: float | None = None
    sl: float | None = None
    tp: float | None = None
    session: str | None = None
    tags: list[str] = Field(default_factory=list)
    planned_risk_usd: float | None = None
    signal_bar_ts: datetime | None = None
    sweep_extreme: float | None = None
    htf_bias: str | None = None


class SimTrade(BaseModel):
    id: str
    signal_id: str
    symbol: str
    side: Side
    decision: Decision
    grade: str | None = None
    session: str | None = None
    fill_ts: datetime | None = None
    fill_price: float | None = None
    initial_sl: float
    current_sl: float
    be_armed: bool = False
    exit_ts: datetime | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    r_multiple: float | None = None
    pnl_usd: float | None = None
    mfe_r: float = 0.0
    mae_r: float = 0.0
    hold_minutes: int | None = None
    planned_risk_usd: float = 100.0
    status: Literal["pending", "open", "closed", "aborted"] = "pending"
    signal_bar_ts: datetime
    weekday: str | None = None


class TvHookPayload(BaseModel):
    symbol: str
    timeframe: str = "M15"
    time: datetime | str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
