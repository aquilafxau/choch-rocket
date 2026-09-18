"""Simple HTML WR tables for the local paper session."""

from __future__ import annotations

from html import escape

from app.models import Signal, SimTrade


def _metrics_table(title: str, metrics: dict) -> str:
    if not metrics or metrics.get("n") == 0:
        return f"<section><h2>{escape(title)}</h2><p>No closed sim trades.</p></section>"
    wr = metrics.get("wr")
    wr_s = f"{wr * 100:.1f}%" if wr is not None else "—"
    rows = "".join(
        f"<tr><th>{escape(k)}</th><td>{escape(str(v))}</td></tr>"
        for k, v in metrics.items()
        if k != "wr"
    )
    return f"""
    <section>
      <h2>{escape(title)}</h2>
      <table>
        <tr><th>win rate</th><td>{wr_s}</td></tr>
        {rows}
      </table>
    </section>
    """


def _nested(title: str, groups: dict) -> str:
    if not groups:
        return f"<section><h2>{escape(title)}</h2><p>None.</p></section>"
    parts = [_metrics_table(f"{title} — {name}", m) for name, m in groups.items()]
    return "".join(parts)


def render_dashboard(summary: dict, signals: list[Signal], trades: list[SimTrade]) -> str:
    overall = _metrics_table("Overall shadow book", summary.get("overall") or {})
    cf = summary.get("counterfactuals") or {}
    counter = "".join(_metrics_table(f"Counterfactual: {k}", v) for k, v in cf.items())
    sig_rows = "".join(
        f"<tr><td>{escape(s.ts.isoformat())}</td><td>{escape(s.symbol)}</td>"
        f"<td>{escape(s.decision)}</td><td>{escape(s.side or '')}</td>"
        f"<td>{escape(s.veto_reason or '')}</td><td>{escape(','.join(s.tags))}</td></tr>"
        for s in signals
    )
    trade_rows = "".join(
        f"<tr><td>{escape(t.symbol)}</td><td>{escape(t.side)}</td><td>{escape(t.status)}</td>"
        f"<td>{t.r_multiple}</td><td>{escape(t.exit_reason or '')}</td><td>{t.pnl_usd}</td></tr>"
        for t in trades
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Choch Rocket — shadow stats</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem; background: #0f1419; color: #e7ecf1; }}
    h1 {{ margin-bottom: 0.2rem; }}
    .banner {{ background: #7a1f1f; color: #fff; padding: 0.6rem 1rem; border-radius: 6px; font-weight: 600; }}
    table {{ border-collapse: collapse; margin: 0.6rem 0 1.4rem; }}
    th, td {{ border: 1px solid #2a3440; padding: 0.35rem 0.7rem; text-align: left; }}
    th {{ background: #1b2430; }}
    a {{ color: #8fd3ff; }}
    section {{ margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <p class="banner">SHADOW ONLY — recommend + paper-sim. No broker. No live orders.</p>
  <h1>Choch Rocket</h1>
  <p>EURUSD + AUDUSD · London 16:00–20:59 AEST · GET <a href="/stats">/stats</a> · <a href="/health">/health</a></p>
  {overall}
  {_nested("By pair", summary.get("by_pair") or {})}
  {_nested("By session", summary.get("by_session") or {})}
  {_nested("By grade", summary.get("by_grade") or {})}
  {_nested("By weekday", summary.get("by_weekday") or {})}
  {counter}
  <section>
    <h2>Signals</h2>
    <table>
      <tr><th>ts</th><th>symbol</th><th>decision</th><th>side</th><th>veto</th><th>tags</th></tr>
      {sig_rows or '<tr><td colspan="6">None yet. Run scripts/replay_day.py</td></tr>'}
    </table>
  </section>
  <section>
    <h2>Sim trades</h2>
    <table>
      <tr><th>symbol</th><th>side</th><th>status</th><th>R</th><th>exit</th><th>$</th></tr>
      {trade_rows or '<tr><td colspan="6">None.</td></tr>'}
    </table>
  </section>
</body>
</html>
"""
