# Choch Rocket 🚀

Local-first Protrend structure monitor: **sweep → CHoCH/MSS → POI** → `GO` / `HALF` / `VETO`, with a **shadow sim** that paper-fills every GO/HALF so win rate and expectancy stay honest.

- **Org:** [aquilafxau](https://github.com/aquilafxau)
- **PRD:** [PRD.md](./PRD.md)
- **P0:** `EURUSD` + `AUDUSD` · London `16:00–20:59 AEST` · recommend + paper-sim only · **no broker orders**
- **P1:** optional NY open `09:00–12:00 America/New_York` (`NY_SESSION_ENABLED=true`) · `NewsCalendar` red-folder ±30m and CPI/FOMC decision-day vetoes
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

## Local NY paper session (P1, off by default)

NY is a second configured window, not a replacement for London. Rails allow **London OR NY** when the flag is on. NY trades flatten at **12:00 America/New_York** (London still flats at **21:00 AEST**).

```bash
uv sync

# Replay the NY Setup A fixture with the NY window enabled
NY_SESSION_ENABLED=true uv run python scripts/replay_day.py \
  --csv data/fixtures/eurusd_m15_ny_setup_a.csv \
  --db data/choch.db

NY_SESSION_ENABLED=true uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
curl -s http://127.0.0.1:8000/health   # ny_session_enabled: true
curl -s http://127.0.0.1:8000/stats
uv run python -m app.stats --db data/choch.db
```

Window knobs: `SESSION_NY=09:00-12:00` (signals `09:00` inclusive through `11:59`; flat at `12:00`), `NY_TIMEZONE=America/New_York`.

Regenerate fixtures:

```bash
uv run python scripts/replay_day.py --dump-fixture data/fixtures/eurusd_m15_setup_a.csv
uv run python scripts/replay_day.py --session ny --dump-fixture data/fixtures/eurusd_m15_ny_setup_a.csv
```

Optional TradingView M15 webhook (still shadow-only — appends a bar and may emit JSON, never an order):

```bash
curl -s -X POST http://127.0.0.1:8000/hooks/tv \
  -H 'content-type: application/json' \
  -d '{"symbol":"EURUSD","timeframe":"M15","time":"2026-03-10T16:45:00+10:00","open":1.08190,"high":1.08340,"low":1.08180,"close":1.08310}'
```

Accept P0 §7 + P1 (NY + news):

```bash
uv run pytest
```

## News calendar

Rails call `NewsCalendar.veto_reason(ts)` only:

- **red-folder** — event timestamp ± 30 minutes (`red_folder_buffer_min`)
- **cpi_fomc** — whole decision day in the event timezone (default `America/New_York`)

Default file: [`data/news_stub.json`](data/news_stub.json). Example:

```json
{
  "source": "stub",
  "red_folder": [
    {"ts": "2026-03-10T08:30:00-04:00", "name": "CPI", "currency": "USD", "impact": "red"}
  ],
  "decision_days": [
    {"date": "2026-03-18", "name": "FOMC", "tz": "America/New_York"}
  ]
}
```

### Swap to Forex Factory later (no rails rewrite)

1. Map FF rows → `RedFolderEvent` (High/Red impact) and `DecisionDay` (CPI / FOMC / rate decision).
2. Implement `ForexFactoryCalendar.fetch()` in `app/rails/calendar.py`.
3. Set `NEWS_SOURCE=forexfactory`. Until `fetch()` exists, that source reads the same JSON cache so `gate.py` does not change.

## What the engine does

1. **HTF bias** from completed H4 (fallback H1).
2. **M15 sweep** of the Asia range (`07:00–15:59` AEST). No sweep = no trade.
3. **CHoCH/MSS** back in the sweep’s direction.
4. Displacement **POI** (FVG, else order block) and **one** retrace.
5. **Rails:** whitelist pairs; London and (if enabled) NY; against-trend = `VETO` (no sim open); red-folder ±30m / CPI-FOMC decision day; stop after 2 sim losses; Wed/Thu `HALF` unless grade `A+`.
6. **Shadow sim** on every `GO`/`HALF`: fill at **next bar open**, SL beyond the sweep (never widened), BE at `+1R` (`SCALP_MODE` → `+0.5R`), flat at **21:00 AEST** (London) or **12:00 America/New_York** (NY). `VETO` is logged only.

## Config knobs

| Env | Default | Notes |
|---|---|---|
| `SHADOW_ONLY` | `true` | Live mode raises |
| `PAIRS` | `EURUSD,AUDUSD` | |
| `SESSION_LONDON` | `16:00-20:59` | AEST |
| `NY_SESSION_ENABLED` | `false` | P1 flag |
| `SESSION_NY` | `09:00-12:00` | America/New_York |
| `RISK_USD` | `100` | |
| `BE_AT_R` | `1.0` | |
| `SCALP_MODE` | `false` | BE at `+0.5R` |
| `NEWS_SOURCE` | `stub` | `forexfactory` selects the FF adapter slot |

## Status

P0 MVP + P1 NY window and news calendar. Still shadow-only.
