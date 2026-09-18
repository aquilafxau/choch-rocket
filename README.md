# Choch Rocket 🚀

Local-first Protrend structure monitor: **sweep → CHoCH/MSS → POI** → `GO` / `HALF` / `VETO`, with a **shadow sim** that paper-fills every GO/HALF so win rate and expectancy stay honest.

- **Org:** [aquilafxau](https://github.com/aquilafxau)
- **PRD:** [PRD.md](./PRD.md)
- **MVP:** EURUSD + AUDUSD · London `16:00–20:59 AEST` · recommendation only · no broker orders

## Quick start (coming with first implementation PR)

```bash
# uv sync && uv run uvicorn app.main:app --reload
# uv run scripts/replay_day.py --csv data/EURUSD_M15.csv
# open http://127.0.0.1:8000/stats
```

## Status

PRD landed. Implementation scaffold next (FastAPI + SQLite + structure detectors + sim book).
