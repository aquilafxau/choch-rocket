"""WR / PF / expectancy / max DD plus rails counterfactuals."""

from __future__ import annotations

from collections import defaultdict

from app.models import SimTrade
from app.timeutil import aest_date, to_aest


def metrics(trades: list[SimTrade]) -> dict:
    closed = [t for t in trades if t.status == "closed" and t.r_multiple is not None]
    n = len(closed)
    if n == 0:
        return {
            "n": 0,
            "wins": 0,
            "losses": 0,
            "wr": None,
            "pf": None,
            "avg_r": None,
            "expectancy_r": None,
            "expectancy_usd": None,
            "max_dd_usd": None,
            "max_dd_r": None,
            "net_usd": 0.0,
            "net_r": 0.0,
        }
    wins = [t for t in closed if (t.r_multiple or 0) > 0]
    losses = [t for t in closed if (t.r_multiple or 0) < 0]
    gross_win = sum(t.pnl_usd or 0.0 for t in wins)
    gross_loss = abs(sum(t.pnl_usd or 0.0 for t in losses))
    net_usd = sum(t.pnl_usd or 0.0 for t in closed)
    net_r = sum(t.r_multiple or 0.0 for t in closed)
    pf = None if gross_loss == 0 else round(gross_win / gross_loss, 4)
    avg_r = net_r / n
    return {
        "n": n,
        "wins": len(wins),
        "losses": len(losses),
        "wr": round(len(wins) / n, 4),
        "pf": pf,
        "avg_r": round(avg_r, 4),
        "expectancy_r": round(avg_r, 4),
        "expectancy_usd": round(net_usd / n, 4),
        "max_dd_usd": round(_max_dd([t.pnl_usd or 0.0 for t in closed]), 2),
        "max_dd_r": round(_max_dd([t.r_multiple or 0.0 for t in closed]), 4),
        "net_usd": round(net_usd, 2),
        "net_r": round(net_r, 4),
    }


def _max_dd(pnl: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for x in pnl:
        equity += x
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    return max_dd


def _group(trades: list[SimTrade], key) -> dict[str, dict]:
    buckets: dict[str, list[SimTrade]] = defaultdict(list)
    for trade in trades:
        buckets[str(key(trade) or "none")].append(trade)
    return {name: metrics(items) for name, items in sorted(buckets.items())}


def stop_after_2l(trades: list[SimTrade], limit: int = 2) -> list[SimTrade]:
    kept: list[SimTrade] = []
    losses: dict = {}
    ordered = sorted(
        [t for t in trades if t.status == "closed"],
        key=lambda t: t.fill_ts or t.signal_bar_ts,
    )
    for trade in ordered:
        day = aest_date(trade.fill_ts or trade.signal_bar_ts)
        if losses.get(day, 0) >= limit:
            continue
        kept.append(trade)
        if (trade.r_multiple or 0) < 0:
            losses[day] = losses.get(day, 0) + 1
    return kept


def summarize(trades: list[SimTrade]) -> dict:
    closed = [t for t in trades if t.status == "closed"]
    return {
        "overall": metrics(closed),
        "by_pair": _group(closed, lambda t: t.symbol),
        "by_session": _group(closed, lambda t: t.session),
        "by_grade": _group(closed, lambda t: t.grade),
        "by_weekday": _group(closed, lambda t: t.weekday or WEEKDAY.get(to_aest(t.signal_bar_ts).weekday())),
        "counterfactuals": {
            "stop_after_2l": metrics(stop_after_2l(closed)),
            "a_plus_only": metrics([t for t in closed if t.grade == "A+"]),
            "london_only": metrics([t for t in closed if t.session == "london"]),
        },
        "shadow_only": True,
    }


WEEKDAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
