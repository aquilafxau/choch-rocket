"""Bar-by-bar orchestrator: detect → rails → recommend → shadow sim."""

from __future__ import annotations

from app.config import Settings
from app.db import Store
from app.ingest.csv_loader import load_csv
from app.models import Bar, Signal
from app.recommend.emit import emit
from app.sim.engine import SimEngine
from app.structure.detect import detect
from app.timeutil import aest_date


class Pipeline:
    def __init__(self, store: Store, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        if not self.settings.shadow_only:
            raise RuntimeError("shadow-only")
        self.store = store
        self.sim = SimEngine(store, self.settings)
        self.emitted: set[str] = set()

    def on_bar(self, bar: Bar) -> Signal | None:
        self.store.insert_bar(bar)
        history = self.store.bars(bar.symbol, bar.timeframe)
        self.sim.on_bar(bar)
        structure = detect(history, self.settings)
        if structure is None:
            return None
        if structure.poi_key in self.emitted:
            return None
        if self._already_taken_today(bar):
            return None
        signal = emit(structure, self.settings, self.store)
        self.emitted.add(structure.poi_key)
        self.store.insert_signal(signal)
        if signal.decision in {"GO", "HALF"}:
            self.sim.queue(signal)
        return signal

    def replay(self, bars: list[Bar]) -> list[Signal]:
        signals: list[Signal] = []
        last: Bar | None = None
        for bar in bars:
            signal = self.on_bar(bar)
            if signal is not None:
                signals.append(signal)
            last = bar
        if last is not None:
            self.sim.finalize(last)
        return signals

    def replay_csv(self, path: str, symbol: str | None = None) -> list[Signal]:
        return self.replay(load_csv(path, symbol=symbol))

    def _already_taken_today(self, bar: Bar) -> bool:
        today = aest_date(bar.ts)
        for signal in self.store.list_signals():
            if signal.symbol != bar.symbol:
                continue
            if aest_date(signal.ts) != today:
                continue
            if signal.decision in {"GO", "HALF"}:
                return True
        return False
