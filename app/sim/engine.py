"""Shadow paper-sim. Next-bar open fill, SL beyond sweep, BE at +1R, flat 21:00 AEST."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.config import Settings
from app.db import Store
from app.models import Bar, Signal, SimTrade
from app.timeutil import to_aest

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class SimEngine:
    def __init__(self, store: Store, settings: Settings) -> None:
        self.store = store
        self.settings = settings

    def queue(self, signal: Signal) -> SimTrade | None:
        if signal.decision not in {"GO", "HALF"}:
            return None
        if signal.side is None or signal.sl is None or signal.signal_bar_ts is None:
            return None
        trade = SimTrade(
            id=str(uuid.uuid4()),
            signal_id=signal.id,
            symbol=signal.symbol,
            side=signal.side,
            decision=signal.decision,
            grade=signal.grade,
            session=signal.session,
            initial_sl=signal.sl,
            current_sl=signal.sl,
            planned_risk_usd=signal.planned_risk_usd or self.settings.risk_usd,
            status="pending",
            signal_bar_ts=signal.signal_bar_ts,
            weekday=WEEKDAYS[to_aest(signal.ts).weekday()],
        )
        self.store.insert_trade(trade)
        return trade

    def on_bar(self, bar: Bar) -> None:
        for trade in self.store.pending_or_open(bar.symbol):
            if trade.status == "pending":
                self._try_fill(trade, bar)
                trade = _reload(self.store, trade.id)
                if trade is None or trade.status != "open":
                    continue
            if trade.status == "open":
                self._manage(trade, bar)

    def finalize(self, last_bar: Bar | None) -> None:
        if last_bar is None:
            return
        for trade in self.store.pending_or_open(last_bar.symbol):
            if trade.status == "pending":
                trade.status = "aborted"
                trade.exit_reason = "no_fill_bar"
                trade.exit_ts = last_bar.ts
                self.store.insert_trade(trade)
            elif trade.status == "open" and trade.fill_ts is not None and trade.fill_price is not None:
                self._close(trade, last_bar.ts, last_bar.close, "session_end")

    def _try_fill(self, trade: SimTrade, bar: Bar) -> None:
        if to_aest(bar.ts) <= to_aest(trade.signal_bar_ts):
            return
        fill = bar.open
        risk = abs(fill - trade.initial_sl)
        if risk <= 1e-9:
            trade.status = "aborted"
            trade.exit_reason = "zero_risk"
            trade.exit_ts = bar.ts
            self.store.insert_trade(trade)
            return
        short = trade.side == "short"
        gapped_through_sl = (short and fill >= trade.initial_sl) or (not short and fill <= trade.initial_sl)
        if gapped_through_sl:
            trade.status = "aborted"
            trade.exit_reason = "gap_through_sl"
            trade.exit_ts = bar.ts
            self.store.insert_trade(trade)
            return
        trade.fill_ts = bar.ts
        trade.fill_price = fill
        trade.status = "open"
        self.store.insert_trade(trade)
        self._manage(trade, bar)

    def _manage(self, trade: SimTrade, bar: Bar) -> None:
        if trade.fill_price is None or trade.fill_ts is None:
            return
        if _is_flatten_bar(bar, self.settings):
            self._close(trade, bar.ts, bar.open, "session_end")
            return

        risk = abs(trade.fill_price - trade.initial_sl)
        short = trade.side == "short"
        if short:
            mfe = (trade.fill_price - bar.low) / risk
            mae = (bar.high - trade.fill_price) / risk
        else:
            mfe = (bar.high - trade.fill_price) / risk
            mae = (trade.fill_price - bar.low) / risk
        trade.mfe_r = max(trade.mfe_r, mfe)
        trade.mae_r = max(trade.mae_r, mae)

        if not trade.be_armed and trade.mfe_r >= self.settings.be_trigger_r:
            trade.be_armed = True
            trade.current_sl = trade.fill_price

        hit_sl = (short and bar.high >= trade.current_sl) or ((not short) and bar.low <= trade.current_sl)
        if hit_sl:
            reason = "be" if trade.be_armed and abs(trade.current_sl - trade.fill_price) <= 1e-9 else "sl"
            self._close(trade, bar.ts, trade.current_sl, reason)
            return
        self.store.insert_trade(trade)

    def _close(self, trade: SimTrade, exit_ts: datetime, exit_price: float, reason: str) -> None:
        if trade.fill_price is None or trade.fill_ts is None:
            return
        risk = abs(trade.fill_price - trade.initial_sl)
        if trade.side == "short":
            r_mult = (trade.fill_price - exit_price) / risk
        else:
            r_mult = (exit_price - trade.fill_price) / risk
        hold = int((to_aest(exit_ts) - to_aest(trade.fill_ts)).total_seconds() // 60)
        trade.exit_ts = exit_ts
        trade.exit_price = exit_price
        trade.exit_reason = reason
        trade.r_multiple = round(r_mult, 4)
        trade.pnl_usd = round(r_mult * trade.planned_risk_usd, 2)
        trade.hold_minutes = hold
        trade.status = "closed"
        self.store.insert_trade(trade)


def _is_flatten_bar(bar: Bar, settings: Settings) -> bool:
    local = to_aest(bar.ts).time().replace(tzinfo=None)
    return local >= settings.flatten_time


def _reload(store: Store, trade_id: str) -> SimTrade | None:
    for trade in store.list_trades():
        if trade.id == trade_id:
            return trade
    return None
