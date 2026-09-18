"""CSV + TradingView webhook ingest. Decisions use only bars at or before now."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from app.models import Bar, TvHookPayload
from app.timeutil import to_aest

TIME_KEYS = ("timestamp", "time", "datetime", "date", "ts")
OPEN_KEYS = ("open", "o")
HIGH_KEYS = ("high", "h")
LOW_KEYS = ("low", "l")
CLOSE_KEYS = ("close", "c")
VOL_KEYS = ("volume", "vol", "v")
SYM_KEYS = ("symbol", "ticker", "pair")


def _pick(row: dict[str, str], keys: tuple[str, ...], default: str | None = None) -> str | None:
    lower = {k.lower().strip(): v for k, v in row.items()}
    for key in keys:
        if key in lower and lower[key] not in (None, ""):
            return lower[key]
    return default


def parse_ts(value: str) -> datetime:
    text = value.strip()
    for candidate in (text, text.replace(" ", "T")):
        try:
            return to_aest(datetime.fromisoformat(candidate))
        except ValueError:
            continue
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y.%m.%d %H:%M"):
        try:
            return to_aest(datetime.strptime(text, fmt))
        except ValueError:
            continue
    raise ValueError(f"Unparseable timestamp: {value}")


def load_csv(path: str | Path, symbol: str | None = None) -> list[Bar]:
    file = Path(path)
    bars: list[Bar] = []
    with file.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            ts_raw = _pick(row, TIME_KEYS)
            if not ts_raw:
                raise ValueError(f"Missing timestamp in row: {row}")
            sym = (_pick(row, SYM_KEYS, symbol or "EURUSD") or "EURUSD").upper().replace("/", "")
            bars.append(
                Bar(
                    ts=parse_ts(ts_raw),
                    open=float(_pick(row, OPEN_KEYS) or 0),
                    high=float(_pick(row, HIGH_KEYS) or 0),
                    low=float(_pick(row, LOW_KEYS) or 0),
                    close=float(_pick(row, CLOSE_KEYS) or 0),
                    volume=float(_pick(row, VOL_KEYS, "0") or 0),
                    symbol=sym,
                    timeframe="M15",
                )
            )
    bars.sort(key=lambda b: b.ts)
    return bars


def bar_from_hook(payload: TvHookPayload) -> Bar:
    ts = payload.time if isinstance(payload.time, datetime) else parse_ts(str(payload.time))
    return Bar(
        ts=to_aest(ts),
        open=payload.open,
        high=payload.high,
        low=payload.low,
        close=payload.close,
        volume=payload.volume,
        symbol=payload.symbol,
        timeframe=payload.timeframe or "M15",
    )


def write_csv(path: str | Path, bars: list[Bar]) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume", "symbol"])
        for bar in bars:
            writer.writerow(
                [
                    to_aest(bar.ts).isoformat(),
                    f"{bar.open:.5f}",
                    f"{bar.high:.5f}",
                    f"{bar.low:.5f}",
                    f"{bar.close:.5f}",
                    int(bar.volume),
                    bar.symbol,
                ]
            )
