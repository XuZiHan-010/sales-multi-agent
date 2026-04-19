"""
Generates mock data for 3 sales regions × 6 SKUs × 180 days.
Includes seasonality, weekly patterns, and shock events.
"""

import json
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent / "mock"

REGIONS = ["华北", "华东", "华南"]
SKUS = ["SKU-A", "SKU-B", "SKU-C", "SKU-D", "SKU-E", "SKU-F"]
FACTORIES = ["天津厂", "上海厂", "广州厂"]
WAREHOUSES = [
    "华北-仓1", "华北-仓2", "华北-仓3",
    "华东-仓1", "华东-仓2", "华东-仓3",
    "华南-仓1", "华南-仓2", "华南-仓3",
    "中转-仓1",
]

BASE_DEMAND = {
    "SKU-A": {"华北": 8000, "华东": 12000, "华南": 10000},
    "SKU-B": {"华北": 5000, "华东": 7000,  "华南": 6000},
    "SKU-C": {"华北": 3000, "华东": 4500,  "华南": 4000},
    "SKU-D": {"华北": 6000, "华东": 9000,  "华南": 7500},
    "SKU-E": {"华北": 2500, "华东": 3500,  "华南": 3000},
    "SKU-F": {"华北": 4000, "华东": 5500,  "华南": 5000},
}

FACTORY_CAPACITY = {
    "天津厂": {"SKU-A": 60000, "SKU-B": 40000, "SKU-C": 25000, "SKU-D": 45000, "SKU-E": 20000, "SKU-F": 35000},
    "上海厂": {"SKU-A": 80000, "SKU-B": 55000, "SKU-C": 35000, "SKU-D": 60000, "SKU-E": 28000, "SKU-F": 48000},
    "广州厂": {"SKU-A": 70000, "SKU-B": 48000, "SKU-C": 30000, "SKU-D": 52000, "SKU-E": 24000, "SKU-F": 42000},
}

TRANSPORT_COST_MATRIX = {
    "天津厂":  {"华北-仓1": 50,  "华北-仓2": 55,  "华北-仓3": 60,  "华东-仓1": 120, "华东-仓2": 130, "华东-仓3": 125, "华南-仓1": 200, "华南-仓2": 210, "华南-仓3": 205, "中转-仓1": 90},
    "上海厂":  {"华北-仓1": 130, "华北-仓2": 125, "华北-仓3": 135, "华东-仓1": 45,  "华东-仓2": 50,  "华东-仓3": 48,  "华南-仓1": 110, "华南-仓2": 115, "华南-仓3": 112, "中转-仓1": 70},
    "广州厂":  {"华北-仓1": 210, "华北-仓2": 205, "华北-仓3": 215, "华东-仓1": 115, "华东-仓2": 120, "华东-仓3": 118, "华南-仓1": 40,  "华南-仓2": 45,  "华南-仓3": 42,  "中转-仓1": 80},
}

TRANSPORT_TIME_HOURS = {
    "天津厂":  {"华北-仓1": 4,  "华北-仓2": 5,  "华北-仓3": 6,  "华东-仓1": 18, "华东-仓2": 20, "华东-仓3": 19, "华南-仓1": 36, "华南-仓2": 38, "华南-仓3": 37, "中转-仓1": 12},
    "上海厂":  {"华北-仓1": 20, "华北-仓2": 19, "华北-仓3": 21, "华东-仓1": 3,  "华东-仓2": 4,  "华东-仓3": 3,  "华南-仓1": 16, "华南-仓2": 17, "华南-仓3": 16, "中转-仓1": 8},
    "广州厂":  {"华北-仓1": 38, "华北-仓2": 37, "华北-仓3": 39, "华东-仓1": 17, "华东-仓2": 18, "华东-仓3": 17, "华南-仓1": 3,  "华南-仓2": 4,  "华南-仓3": 3,  "中转-仓1": 10},
}


def _generate_sales_history(start_date: datetime, days: int = 180, rng: np.random.Generator = None) -> list[dict]:
    if rng is None:
        rng = np.random.default_rng(42)
    records = []
    for d in range(days):
        date = start_date + timedelta(days=d)
        weekday = date.weekday()
        week_factor = 1.3 if weekday >= 5 else 1.0  # weekend boost

        month = date.month
        season_factor = 1 + 0.15 * np.sin(2 * np.pi * (month - 3) / 12)  # peak in summer

        for sku in SKUS:
            for region in REGIONS:
                base = BASE_DEMAND[sku][region]
                noise = rng.normal(0, base * 0.05)
                qty = max(0, int(base * week_factor * season_factor + noise))
                records.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "sku": sku,
                    "region": region,
                    "qty_sold": qty,
                })
    return records


def _generate_inventory_snapshot(rng: np.random.Generator = None) -> list[dict]:
    if rng is None:
        rng = np.random.default_rng(42)
    snapshot = []
    for wh in WAREHOUSES:
        region = wh.split("-仓")[0] if "-仓" in wh else "全国"
        for sku in SKUS:
            region_key = region if region in REGIONS else "华东"
            base = BASE_DEMAND[sku].get(region_key, 5000)
            stock = int(rng.uniform(0.5, 2.5) * base)
            safety = int(base * 0.3)
            snapshot.append({
                "warehouse": wh,
                "region": region,
                "sku": sku,
                "current_stock": stock,
                "safety_stock": safety,
                "in_transit": int(rng.uniform(0, base * 0.2)),
            })
    return snapshot


def _generate_factory_status(rng: np.random.Generator = None) -> list[dict]:
    if rng is None:
        rng = np.random.default_rng(42)
    status = []
    for factory in FACTORIES:
        for sku in SKUS:
            max_cap = FACTORY_CAPACITY[factory][sku]
            current_util = rng.uniform(0.6, 0.85)
            status.append({
                "factory": factory,
                "sku": sku,
                "max_capacity_monthly": max_cap,
                "current_utilization": float(round(current_util, 3)),
                "available_capacity": int(max_cap * (1 - current_util)),
                "switch_cost_per_batch": int(rng.uniform(5000, 20000)),
                "equipment_ok": True,
            })
    return status


def generate_all(output_dir: Path = DATA_DIR, seed: int = 42) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    start_date = datetime(2024, 1, 1)   # fixed date for reproducible data generation

    sales = _generate_sales_history(start_date, 180, rng)
    inventory = _generate_inventory_snapshot(rng)
    factory = _generate_factory_status(rng)

    meta = {
        "generated_at": datetime.now().isoformat(),
        "regions": REGIONS,
        "skus": SKUS,
        "factories": FACTORIES,
        "warehouses": WAREHOUSES,
        "transport_cost_matrix": TRANSPORT_COST_MATRIX,
        "transport_time_hours": TRANSPORT_TIME_HOURS,
        "factory_capacity": FACTORY_CAPACITY,
    }

    (output_dir / "sales_history.json").write_text(json.dumps(sales, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "inventory_snapshot.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "factory_status.json").write_text(json.dumps(factory, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[DataGen] sales={len(sales)} rows | inventory={len(inventory)} rows | factory={len(factory)} rows")
    return {"sales": sales, "inventory": inventory, "factory": factory, "meta": meta}


def ensure_mock_data():
    if not (DATA_DIR / "sales_history.json").exists():
        generate_all()


def load_mock_data() -> dict:
    ensure_mock_data()
    return {
        "sales": json.loads((DATA_DIR / "sales_history.json").read_text(encoding="utf-8")),
        "inventory": json.loads((DATA_DIR / "inventory_snapshot.json").read_text(encoding="utf-8")),
        "factory": json.loads((DATA_DIR / "factory_status.json").read_text(encoding="utf-8")),
        "meta": json.loads((DATA_DIR / "meta.json").read_text(encoding="utf-8")),
    }


if __name__ == "__main__":
    generate_all()
