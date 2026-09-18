"""Replay a CSV day through the pipeline (recommend + shadow sim only)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import Settings
from app.db import Store
from app.ingest.csv_loader import load_csv, write_csv
from app.ingest.synthetic import build_ny_setup_a_bars, build_setup_a_bars
from app.pipeline import Pipeline
from app.stats.compute import summarize


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Replay M15 CSV through Choch Rocket (shadow-only)")
    parser.add_argument("--csv", help="M15 OHLC CSV path")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--db", default=None)
    parser.add_argument("--dump-fixture", metavar="PATH", help="Write a synthetic Setup A CSV and exit")
    parser.add_argument(
        "--session",
        choices=("london", "ny"),
        default="london",
        help="Which synthetic path to dump (london AEST vs NY 09:00 ET)",
    )
    args = parser.parse_args(argv)

    if args.dump_fixture:
        bars = build_ny_setup_a_bars() if args.session == "ny" else build_setup_a_bars()
        write_csv(args.dump_fixture, bars)
        print(f"wrote {args.dump_fixture} ({len(bars)} bars, session={args.session})")
        return

    if not args.csv:
        parser.error("--csv is required unless --dump-fixture is set")

    settings = Settings(db_path=args.db) if args.db else Settings()
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    store = Store(settings.db_path)
    pipeline = Pipeline(store, settings)
    signals = pipeline.replay_csv(args.csv, symbol=args.symbol)
    stats = summarize(store.list_trades())
    print(json.dumps(
        {
            "csv": args.csv,
            "signals": [s.model_dump(mode="json") for s in signals],
            "stats": stats,
        },
        indent=2,
    ))
    store.close()


if __name__ == "__main__":
    main()
