"""Fail the build if broker / order-send APIs appear. P0 is shadow-only."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = [ROOT / "app", ROOT / "scripts"]

FORBIDDEN = (
    "place_order(",
    "order_send(",
    "create_order(",
    "submit_order(",
    "send_order(",
    "market_order(",
    "limit_order(",
    "create_market_order",
    "MetaTrader5",
    "import ccxt",
    "from ccxt",
    "ib_insync",
    "alpaca.trading",
    "oandapy",
    "fxcmpy",
    "OrderSend",
    "mt5.order",
)


def test_shadow_only_default():
    assert Settings().shadow_only is True


def test_live_mode_rejected():
    with pytest.raises(ValidationError):
        Settings(shadow_only=False)


def test_no_order_apis_in_source():
    hits: list[str] = []
    for folder in SCAN_DIRS:
        for path in folder.rglob("*.py"):
            text = path.read_text()
            for needle in FORBIDDEN:
                if needle in text:
                    hits.append(f"{path.relative_to(ROOT)}: {needle}")
    assert hits == [], f"broker/order APIs are forbidden in P0:\n" + "\n".join(hits)
