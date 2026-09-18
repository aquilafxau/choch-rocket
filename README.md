# Choch Rocket 🚀

Local-first Protrend structure monitor: **sweep → CHoCH/MSS → POI** → `GO` / `HALF` / `VETO`, with a **shadow sim** that paper-fills every GO/HALF so win rate and expectancy stay honest.

- **Org:** [aquilafxau](https://github.com/aquilafxau)
- **PRD:** [PRD.md](./PRD.md)
- **MVP (P0):** `EURUSD` + `AUDUSD` · London `16:00–20:59 AEST` · recommend + paper-sim only · **no broker orders**
- **Default:** `SHADOW_ONLY=true` (live mode is rejected at config load)

## Local London paper session

Requires **Python 3.12** and [uv](https://docs.astral.sh/uv/).

```bash
uv sync

# 1) Replay the synthetic Tuesday London Setup A fixture into SQLite
uv run python scripts/replay_day.py --csv data/fixtures/eurusd_m15_setup_a.csv

# 2) Serve stats (leave this running during the session window)
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3) Inspect the shadow book
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/stats
# browser: http://127.0.0.1:8000/

# CLI stats (same SQLite file)
uv run python -m app.stats --db data/choch.db
```

Optional TradingView M15 webhook (still shadow-only — appends a bar and may emit JSON, never an order):

```bash
curl -s -X POST http://127.0.0.1:8000/hooks/tv \
  -H 'content-type: application/json' \
  -d '{"symbol":"EURUSD","timeframe":"M15","time":"2026-03-10T16:45:00+10:00","open":1.08190,"high":1.08340,"low":1.08180,"close":1.08310}'
```

Regenerate the synthetic fixture if you change the generator:

```bash
uv run python scripts/replay_day.py --dump-fixture data/fixtures/eurusd_m15_setup_a.csv
```

Accept the P0 suite (PRD §7):

```bash
uv run pytest
```

## What the engine does

1. **HTF bias** from completed H4 (fallback H1).
2. **M15 sweep** of the Asia range (`07:00–15:59` AEST). No sweep = no trade.
3. **CHoCH/MSS** back in the sweep’s direction.
4. Displacement **POI** (FVG, else order block) and **one** retrace.
5. **Rails:** whitelist pairs, London only, against-trend = `VETO` (no sim open), stub red-folder / CPI-FOMC calendar, stop after 2 sim losses, Wed/Thu `HALF` unless grade `A+`.
6. **Shadow sim** on every `GO`/`HALF`: fill at **next bar open**, SL beyond the sweep (never widened), BE at `+1R` (`SCALP_MODE` → `+0.5R`), flat at **21:00 AEST**. `VETO` is logged only.

## Config knobs

Environment variables (all optional): `PAIRS`, `SESSION_LONDON`, `SESSION_NY`, `RISK_USD`, `BE_AT_R`, `SCALP_MODE`, `SHADOW_ONLY`, plus `CHOCH_DB_PATH` via `Settings.db_path`.

`SESSION_NY` is parsed but **off** in v0 (`ny_session_enabled=false`).

## Status

P0 MVP: FastAPI + SQLite + deterministic structure path + shadow book + pytest acceptance.
