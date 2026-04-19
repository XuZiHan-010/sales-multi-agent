"""
In-memory inventory state that persists across scenario runs (simulating WMS).

On first access, initialised from mock JSON. After each run, awarded quantities
are deducted so subsequent runs start from the depleted state.
"""

from __future__ import annotations
import copy
from typing import TYPE_CHECKING

_live_inventory: list[dict] | None = None


def get_live_inventory() -> list[dict]:
    """Return current inventory snapshot, initialising from mock data if needed."""
    global _live_inventory
    if _live_inventory is None:
        from data.generate_mock_data import load_mock_data
        _live_inventory = copy.deepcopy(load_mock_data()["inventory"])
    return _live_inventory


def reset_inventory() -> None:
    """Reset to mock defaults (called by /inventory/reset endpoint)."""
    global _live_inventory
    _live_inventory = None


def apply_negotiation_result(result: dict) -> None:
    """Deduct accepted bid quantities from live inventory after a run completes."""
    inv = get_live_inventory()
    # Build index for fast lookup: (warehouse, sku) → row
    idx: dict[tuple[str, str], dict] = {}
    for row in inv:
        idx[(row["warehouse"], row["sku"])] = row

    for nr in result.get("negotiation_results", []):
        for bid in (nr.get("trace") or []):
            if bid.get("status") != "ACCEPTED":
                continue
            warehouse = bid.get("warehouse")
            sku = bid.get("sku")
            qty = int(bid.get("awarded_qty") or 0)
            if not warehouse or not sku or qty <= 0:
                continue
            row = idx.get((warehouse, sku))
            if row is not None:
                row["current_stock"] = max(0, row["current_stock"] - qty)
