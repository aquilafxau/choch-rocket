"""SQLite persistence for bars, signals, and shadow sim trades."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from app.models import Bar, Signal, SimTrade
from app.timeutil import iso, to_aest

SCHEMA = """
CREATE TABLE IF NOT EXISTS bars (
    symbol TEXT NOT NULL,
    ts TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL DEFAULT 0,
    timeframe TEXT NOT NULL DEFAULT 'M15',
    PRIMARY KEY (symbol, ts, timeframe)
);

CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT,
    grade TEXT,
    decision TEXT NOT NULL,
    veto_reason TEXT,
    entry REAL,
    sl REAL,
    tp REAL,
    session TEXT,
    tags TEXT,
    planned_risk_usd REAL,
    signal_bar_ts TEXT,
    sweep_extreme REAL,
    htf_bias TEXT
);

CREATE TABLE IF NOT EXISTS sim_trades (
    id TEXT PRIMARY KEY,
    signal_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    decision TEXT NOT NULL,
    grade TEXT,
    session TEXT,
    fill_ts TEXT,
    fill_price REAL,
    initial_sl REAL NOT NULL,
    current_sl REAL NOT NULL,
    be_armed INTEGER NOT NULL DEFAULT 0,
    exit_ts TEXT,
    exit_price REAL,
    exit_reason TEXT,
    r_multiple REAL,
    pnl_usd REAL,
    mfe_r REAL NOT NULL DEFAULT 0,
    mae_r REAL NOT NULL DEFAULT 0,
    hold_minutes INTEGER,
    planned_risk_usd REAL NOT NULL DEFAULT 100,
    status TEXT NOT NULL,
    signal_bar_ts TEXT NOT NULL,
    weekday TEXT,
    FOREIGN KEY (signal_id) REFERENCES signals(id)
);
"""


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def insert_bar(self, bar: Bar) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO bars(symbol, ts, open, high, low, close, volume, timeframe)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bar.symbol,
                iso(bar.ts),
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
                bar.timeframe,
            ),
        )
        self.conn.commit()

    def bars(self, symbol: str, timeframe: str = "M15") -> list[Bar]:
        rows = self.conn.execute(
            "SELECT * FROM bars WHERE symbol = ? AND timeframe = ? ORDER BY ts ASC",
            (symbol.upper().replace("/", ""), timeframe),
        ).fetchall()
        return [
            Bar(
                symbol=r["symbol"],
                ts=_parse_ts(r["ts"]),
                open=r["open"],
                high=r["high"],
                low=r["low"],
                close=r["close"],
                volume=r["volume"],
                timeframe=r["timeframe"],
            )
            for r in rows
        ]

    def insert_signal(self, signal: Signal) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO signals(
                id, ts, symbol, side, grade, decision, veto_reason, entry, sl, tp,
                session, tags, planned_risk_usd, signal_bar_ts, sweep_extreme, htf_bias
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal.id,
                iso(signal.ts),
                signal.symbol,
                signal.side,
                signal.grade,
                signal.decision,
                signal.veto_reason,
                signal.entry,
                signal.sl,
                signal.tp,
                signal.session,
                json.dumps(signal.tags),
                signal.planned_risk_usd,
                iso(signal.signal_bar_ts) if signal.signal_bar_ts else None,
                signal.sweep_extreme,
                signal.htf_bias,
            ),
        )
        self.conn.commit()

    def list_signals(self) -> list[Signal]:
        rows = self.conn.execute("SELECT * FROM signals ORDER BY ts ASC").fetchall()
        out: list[Signal] = []
        for r in rows:
            out.append(
                Signal(
                    id=r["id"],
                    ts=_parse_ts(r["ts"]),
                    symbol=r["symbol"],
                    side=r["side"],
                    grade=r["grade"],
                    decision=r["decision"],
                    veto_reason=r["veto_reason"],
                    entry=r["entry"],
                    sl=r["sl"],
                    tp=r["tp"],
                    session=r["session"],
                    tags=json.loads(r["tags"] or "[]"),
                    planned_risk_usd=r["planned_risk_usd"],
                    signal_bar_ts=_parse_ts(r["signal_bar_ts"]),
                    sweep_extreme=r["sweep_extreme"],
                    htf_bias=r["htf_bias"],
                )
            )
        return out

    def insert_trade(self, trade: SimTrade) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO sim_trades(
                id, signal_id, symbol, side, decision, grade, session, fill_ts, fill_price,
                initial_sl, current_sl, be_armed, exit_ts, exit_price, exit_reason,
                r_multiple, pnl_usd, mfe_r, mae_r, hold_minutes, planned_risk_usd,
                status, signal_bar_ts, weekday
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.id,
                trade.signal_id,
                trade.symbol,
                trade.side,
                trade.decision,
                trade.grade,
                trade.session,
                iso(trade.fill_ts) if trade.fill_ts else None,
                trade.fill_price,
                trade.initial_sl,
                trade.current_sl,
                int(trade.be_armed),
                iso(trade.exit_ts) if trade.exit_ts else None,
                trade.exit_price,
                trade.exit_reason,
                trade.r_multiple,
                trade.pnl_usd,
                trade.mfe_r,
                trade.mae_r,
                trade.hold_minutes,
                trade.planned_risk_usd,
                trade.status,
                iso(trade.signal_bar_ts),
                trade.weekday,
            ),
        )
        self.conn.commit()

    def list_trades(self) -> list[SimTrade]:
        rows = self.conn.execute("SELECT * FROM sim_trades ORDER BY signal_bar_ts ASC").fetchall()
        return [_row_to_trade(r) for r in rows]

    def pending_or_open(self, symbol: str | None = None) -> list[SimTrade]:
        sql = "SELECT * FROM sim_trades WHERE status IN ('pending', 'open')"
        params: tuple = ()
        if symbol:
            sql += " AND symbol = ?"
            params = (symbol,)
        rows = self.conn.execute(sql, params).fetchall()
        return [_row_to_trade(r) for r in rows]

    def losses_on_date(self, day) -> int:
        rows = self.conn.execute(
            "SELECT exit_ts, r_multiple, status FROM sim_trades WHERE status = 'closed'"
        ).fetchall()
        n = 0
        for r in rows:
            if r["r_multiple"] is None or r["r_multiple"] >= 0:
                continue
            ts = _parse_ts(r["exit_ts"])
            if ts and to_aest(ts).date() == day:
                n += 1
        return n

    def open_count(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM sim_trades WHERE status IN ('pending', 'open')"
        ).fetchone()
        return int(row["n"])


def _row_to_trade(r: sqlite3.Row) -> SimTrade:
    return SimTrade(
        id=r["id"],
        signal_id=r["signal_id"],
        symbol=r["symbol"],
        side=r["side"],
        decision=r["decision"],
        grade=r["grade"],
        session=r["session"],
        fill_ts=_parse_ts(r["fill_ts"]),
        fill_price=r["fill_price"],
        initial_sl=r["initial_sl"],
        current_sl=r["current_sl"],
        be_armed=bool(r["be_armed"]),
        exit_ts=_parse_ts(r["exit_ts"]),
        exit_price=r["exit_price"],
        exit_reason=r["exit_reason"],
        r_multiple=r["r_multiple"],
        pnl_usd=r["pnl_usd"],
        mfe_r=r["mfe_r"],
        mae_r=r["mae_r"],
        hold_minutes=r["hold_minutes"],
        planned_risk_usd=r["planned_risk_usd"],
        status=r["status"],
        signal_bar_ts=_parse_ts(r["signal_bar_ts"]),
        weekday=r["weekday"],
    )
