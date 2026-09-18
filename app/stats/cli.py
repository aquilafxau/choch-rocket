"""CLI: python -m app.stats [--db data/choch.db]"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import Settings
from app.db import Store
from app.stats.compute import summarize


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Choch Rocket shadow-sim stats")
    parser.add_argument("--db", default=None, help="SQLite path (default: settings.db_path)")
    args = parser.parse_args(argv)
    settings = Settings()
    path = Path(args.db or settings.db_path)
    store = Store(path)
    print(json.dumps(summarize(store.list_trades()), indent=2))
    store.close()


if __name__ == "__main__":
    main()
