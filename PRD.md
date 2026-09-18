# Choch Rocket — Product Requirements Document

**Codename:** Choch Rocket (formerly Aquila Sentinel)  
**Owner org:** `aquilafxau`  
**Strategy root:** AquilaFX-Protrend-M15 (with-trend London continuation: sweep → CHoCH/MSS → POI)  
**Status:** Local MVP first → AWS later  
**Default mode:** Shadow-only (recommend + paper-sim; **no auto-orders**)

---

## 1. Problem

Protrend edge prints when process is followed (with-trend, London, EUR/AUD, Setup A). As-traded books are ~flat because of process leaks (against-trend, off-pair, FOMO, trading after 2 losses). We need a system that:

1. Watches charts for Protrend structure in real time.
2. Emits **GO / HALF / VETO** recommendations in London (and later NY open).
3. **Paper-fills every GO/HALF** so win rate, PF, and expectancy are measured continuously — even when no live trade is taken.
4. Makes against-trend / off-session / off-plan hard to “accidentally” greenlight.

Henry enters/exits. Choch Rocket never places broker orders in MVP.

---

## 2. Goals

| Priority | Goal |
|---|---|
| P0 | Local app: CSV/webhook ingest → structure detect → rails gate → signal → shadow sim → `/stats` WR |
| P0 | Pairs: `EURUSD` + `AUDUSD` only |
| P0 | Session: London `16:00–20:59 AEST` |
| P0 | Against-trend = auto VETO (no sim open) |
| P1 | NY open window (configurable, e.g. 09:00–12:00 ET) |
| P1 | News/calendar stub → real FF feed |
| P2 | AWS lift (Fargate + RDS) without rewrite |
| P2 | AI narrative / chart vision (assist only; rails dispose) |
| Out | Auto-order execution (separate armed agent later) |

---

## 3. Non-goals (v0)

- AWS / multi-region
- Bedrock vision as sole GO authority
- “Any chart” without unlock ladder
- TradeZella Rating as a pre-trade filter
- Live prop trading / broker keys

---

## 4. Users

- **Henry** — reads GO/HALF/VETO; optionally takes live; reviews `/stats`
- **Protrend Desk (bot)** — merges fundamentals flats with structure signals
- **Cursor / local runner** — builds and runs the MVP

---

## 5. Functional requirements

### 5.1 Ingest
- Load historical M15 (and later M5) OHLC CSV for replay
- Optional TradingView webhook: `POST /hooks/tv`
- No lookahead: decisions use only bars available at signal time

### 5.2 Structure engine (deterministic)
Detect, in order:
1. HTF directional bias (H1/H4 config)
2. M15 liquidity **sweep** of Asia/session H/L or equal H/L
3. **CHoCH/MSS** shift back with HTF
4. Displacement → **POI** (FVG/OB)
5. One retrace into POI  
**No sweep = no trade.**

### 5.3 Rails gate
Hard VETO if any:
- Outside London (v0) / outside configured sessions
- Pair not in `{EURUSD, AUDUSD}`
- Against HTF trend
- Red-folder ±30m (stub calendar in v0)
- CPI/FOMC decision day (stub)
- Day already stopped after 2 **sim or live** losses (config)
- Note smells FOMO / revenge / not-in-plan (optional NLP later; v0 skip)

HALF size path: Wed/Thu unless A+; or 2Y flat regime (config stub).

### 5.4 Recommendation
Emit JSON signal:
```json
{
  "id": "...",
  "ts": "...",
  "symbol": "EURUSD",
  "side": "short",
  "grade": "A",
  "decision": "GO|HALF|VETO",
  "veto_reason": null,
  "entry": 1.08,
  "sl": 1.082,
  "tp": null,
  "session": "london",
  "tags": ["with_trend", "sweep", "choch", "poi", "setup_a"],
  "planned_risk_usd": 100
}
```

### 5.5 Shadow sim (core)
On every **GO** and **HALF**:
1. Open paper position at **next bar open** after signal bar
2. SL beyond sweep; never widen
3. BE at +1R (scalp mode: +0.5R configurable)
4. Flat at session end / 21:00 AEST
5. Record R, $, MFE, MAE, hold time, `exit_reason`

**VETO** → log only, **no** open.

### 5.6 Stats
`GET /stats` and CLI:
- Overall WR, PF, avg R, expectancy, max DD
- By pair, session, grade, weekday
- Counterfactuals: stop-after-2L, A+ only, London only
- Human delta later: sim vs live takes

---

## 6. Local stack

- Python 3.12 + uv/Poetry
- FastAPI
- SQLite (signals + sim_trades)
- APScheduler or external cron for windows
- Streamlit or simple HTML for WR tables
- Pytest acceptance suite

### Repo layout
```
choch-rocket/
  README.md
  PRD.md
  pyproject.toml
  app/
    main.py
    config.py
    ingest/
    structure/
    rails/
    recommend/
    sim/
    stats/
    models.py
  data/
  tests/
  scripts/replay_day.py
```

---

## 7. Acceptance tests (MVP done when)

- [ ] Replay fixture day → ≥1 Setup A path emits GO/HALF with tags
- [ ] Against-trend → VETO, zero sim open
- [ ] Outside London → VETO
- [ ] GO → sim row closes with R + exit_reason
- [ ] `/stats` WR matches manual count on fixture
- [ ] No lookahead fills

---

## 8. Config knobs

`PAIRS`, `SESSION_LONDON`, `SESSION_NY` (off in v0), `RISK_USD`, `BE_AT_R`, `SCALP_MODE`, `SHADOW_ONLY=true`

---

## 9. Unlock ladder

1. Shadow-only EUR/AUD London  
2. Add NY window  
3. Real news feed  
4. Live unlock only after shadow thresholds (WR/expectancy on A+ London) agreed with CoS  
5. AWS lift  

---

## 10. One-liner

**Choch Rocket:** shift confirmed → launch recommendation → sim always takes → stats prove the edge → live only when the shadow book prints.
