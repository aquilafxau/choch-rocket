#!/usr/bin/env python3
"""CLI wrapper: uv run python scripts/replay_day.py --csv data/fixtures/eurusd_m15_setup_a.csv"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.replay import main

if __name__ == "__main__":
    main()
