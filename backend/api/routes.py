"""
FastAPI routes.
"""

import asyncio
import json
import threading
import uuid
from collections import OrderedDict
from typing import AsyncGenerator

import numpy as np
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from data.generate_mock_data import load_mock_data
from data.inventory_state import get_live_inventory, reset_inventory, apply_negotiation_result


def _convert_to_serializable(obj):
    """Convert NumPy types to Python native types for JSON serialization."""
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _convert_to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_convert_to_serializable(item) for item in obj]
    return obj

router = APIRouter()

# In-memory run store (LRU, max 30 entries) + lock for thread-safe writes
_MAX_RUNS = 30
_runs: OrderedDict[str, dict] = OrderedDict()
_runs_lock = threading.Lock()


def _set_run(run_id: str, value: dict) -> None:
    with _runs_lock:
        _runs[run_id] = value
        _runs.move_to_end(run_id)
        while len(_runs) > _MAX_RUNS:
            _runs.popitem(last=False)


def _update_run(run_id: str, **kwargs) -> None:
    with _runs_lock:
        if run_id in _runs:
            _runs[run_id].update(kwargs)


# ── Static data ───────────────────────────────────────────────────────────────

@router.get("/meta")
async def get_meta():
    return load_mock_data()["meta"]


@router.get("/inventory")
async def get_inventory():
    return load_mock_data()["inventory"]


@router.get("/inventory/live")
async def get_live_inventory_endpoint():
    """Current inventory state — decrements after each run (simulates WMS)."""
    return get_live_inventory()


@router.post("/inventory/reset")
async def reset_inventory_endpoint():
    """Reset inventory to mock defaults."""
    reset_inventory()
    return {"status": "reset", "message": "库存已重置为初始状态"}


@router.get("/factory")
async def get_factory():
    return load_mock_data()["factory"]


@router.get("/sales/history")
async def get_sales_history(region: str | None = None, sku: str | None = None):
    records = load_mock_data()["sales"]
    if region:
        records = [r for r in records if r["region"] == region]
    if sku:
        records = [r for r in records if r["sku"] == sku]
    return records


# ── Scenario execution ────────────────────────────────────────────────────────

BUILTIN_SCENARIOS = {
    "main": {
        "name": "直播爆单 + 工厂故障",
        "demand_shocks": {},
        "factory_faults": {},
        "market_signals": [
            {
                "signal_type": "livestream",
                "region": "华南",
                "sku": "SKU-A",
                "demand_multiplier": 3.0,
                "duration_hours": 48,
                "description": "头部主播直播带货 SKU-A，预计带动华南区需求激增 3 倍",
                "source": "livestream_calendar",
            },
            {
                "signal_type": "supply_shock",
                "region": None,
                "sku": "SKU-A",
                "demand_multiplier": 1.0,
                "duration_hours": 24,
                "description": "广州厂 SKU-A 产线设备故障，产能下降 30%",
                "source": "iot_monitor",
                "factory_fault": {"factory": "广州厂", "skus": ["SKU-A"]},
            },
        ],
    },
    "competitor": {
        "name": "竞品促销抢单",
        "demand_shocks": {},
        "factory_faults": {},
        "market_signals": [
            {
                "signal_type": "competitor",
                "region": "华东",
                "sku": "SKU-B",
                "demand_multiplier": 2.0,
                "duration_hours": 72,
                "description": "竞品促销活动，华东 SKU-B 预计承接溢出需求",
                "source": "competitor_monitor",
            },
        ],
    },
    "weather": {
        "name": "华南高温气候冲击",
        "demand_shocks": {},
        "factory_faults": {},
        "market_signals": [
            {
                "signal_type": "weather",
                "region": "华南",
                "sku": "SKU-A",
                "demand_multiplier": 1.5,
                "duration_hours": 96,
                "description": "华南地区高温预警（>38°C），功能饮料需求上涨 50%",
                "source": "weather_api",
            },
        ],
    },
}


class ScenarioRequest(BaseModel):
    scenario_id: str = "main"
    demand_shocks: dict | None = None
    factory_faults: dict | None = None
    market_signals: list | None = None


def _run_scenario_sync(run_id: str, scenario_name: str, demand_shocks: dict, factory_faults: dict, market_signals: list):
    import logging
    from graph.negotiation_graph import run_scenario
    _logger = logging.getLogger(__name__)
    try:
        _update_run(run_id, status="running")

        def on_event(full_event_log):
            _update_run(run_id, event_log=list(full_event_log))

        result = run_scenario(
            scenario_name=scenario_name,
            demand_shocks=demand_shocks,
            factory_faults=factory_faults,
            market_signals=market_signals,
            on_event=on_event,
        )
        apply_negotiation_result(result)
        _set_run(run_id, {**result, "run_id": run_id})
    except Exception as e:
        _logger.exception("[routes] run %s failed", run_id)
        _update_run(run_id, status="error", error=str(e))


@router.get("/scenarios")
async def list_scenarios():
    return [
        {"id": k, "name": v["name"]}
        for k, v in BUILTIN_SCENARIOS.items()
    ]


@router.post("/run")
async def run_scenario_endpoint(req: ScenarioRequest, background_tasks: BackgroundTasks):
    run_id = str(uuid.uuid4())
    if req.scenario_id not in BUILTIN_SCENARIOS and not (req.market_signals or req.demand_shocks):
        raise HTTPException(status_code=422, detail=f"Unknown scenario_id '{req.scenario_id}'")
    scenario = BUILTIN_SCENARIOS.get(req.scenario_id, BUILTIN_SCENARIOS["main"])

    demand_shocks = req.demand_shocks or scenario["demand_shocks"]
    factory_faults = req.factory_faults or scenario["factory_faults"]
    market_signals = req.market_signals or scenario.get("market_signals", [])
    scenario_name = scenario["name"]

    _set_run(run_id, {"run_id": run_id, "status": "pending", "event_log": []})
    background_tasks.add_task(
        _run_scenario_sync, run_id, scenario_name, demand_shocks, factory_faults, market_signals
    )
    return {"run_id": run_id, "status": "pending"}


@router.get("/result/{run_id}")
async def get_result(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    return _convert_to_serializable(_runs[run_id])


@router.get("/history")
async def get_history():
    result = [
        {
            "run_id": v.get("run_id"),
            "scenario_name": v.get("scenario_name"),
            "status": v.get("status"),
            "awarded": sum(_convert_to_serializable(r.get("awarded_qty", 0)) for r in v.get("negotiation_results", [])),
            "total_cost": sum(_convert_to_serializable(r.get("total_cost", 0)) for r in v.get("negotiation_results", [])),
        }
        for v in _runs.values()
    ]
    return _convert_to_serializable(result)


# ── SSE event stream ──────────────────────────────────────────────────────────

async def _event_generator(run_id: str) -> AsyncGenerator[str, None]:
    sent_count = 0
    for _ in range(600):     # poll up to 300s (slow LLM runs)
        await asyncio.sleep(0.5)
        run = _runs.get(run_id, {})
        log = run.get("event_log", [])

        for ev in log[sent_count:]:
            yield f"data: {json.dumps(_convert_to_serializable(ev), ensure_ascii=False)}\n\n"
            sent_count += 1

        if run.get("status") in ("done", "error"):
            yield f"data: {json.dumps({'type': 'stream_end', 'status': run['status']})}\n\n"
            break


@router.get("/events/{run_id}")
async def sse_events(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    return StreamingResponse(
        _event_generator(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
