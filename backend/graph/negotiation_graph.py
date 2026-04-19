"""
LangGraph-based negotiation orchestration graph.

State machine nodes (M3):
  sense_signal → federated_forecast → sense_demand → apply_faults
  → broadcast_cfp → finalize

Each node updates the shared GraphState and appends to the event log
(used by the frontend SSE stream).
"""

from __future__ import annotations
import logging
import uuid
from datetime import datetime, timedelta

from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

from protocols.fipa_acl import NegotiationBus
from agents.inventory_agent import InventoryAgent
from agents.production_agent import ProductionAgent
from agents.coordinator_agent import CoordinatorAgent, NegotiationResult
from data.generate_mock_data import load_mock_data, FACTORIES, WAREHOUSES
from data.inventory_state import get_live_inventory

logger = logging.getLogger(__name__)


# ── Graph State ───────────────────────────────────────────────────────────────

class GraphState(TypedDict):
    scenario_id: str
    scenario_name: str
    demand_shocks: dict[str, dict[str, float]]   # region → {sku: multiplier}
    factory_faults: dict[str, list[str]]          # factory → [skus affected]
    market_signals: list[dict]                    # raw signals from MarketSignalAgent
    federated_forecasts: dict                     # sku → GlobalDemandView summary
    shortage_events: list[dict]                   # [{sku, qty, region}]
    negotiation_results: list[dict]
    event_log: list[dict]
    status: str                                   # "running" | "done" | "error"
    error: str | None


def _log_event(state: GraphState, event_type: str, payload: dict) -> dict:
    entry = {
        "id": str(uuid.uuid4())[:8],
        "timestamp": datetime.utcnow().isoformat(),
        "type": event_type,
        **payload,
    }
    return entry


# ── Node implementations ──────────────────────────────────────────────────────

def node_sense_signal(state: GraphState) -> GraphState:
    """
    M3: Market Signal Agent reads injected events and enriches demand_shocks
    and factory_faults from signal content.
    """
    from agents.market_signal_agent import MarketSignalAgent, MOCK_EVENTS
    events = list(state.get("event_log", []))
    market_signals = list(state.get("market_signals", []))

    bus = NegotiationBus()
    agent = MarketSignalAgent(bus)

    # Re-derive shocks from pre-injected market_signals (set during scenario setup)
    demand_shocks = dict(state.get("demand_shocks", {}))
    factory_faults = dict(state.get("factory_faults", {}))

    for signal in market_signals:
        stype = signal.get("signal_type", "")
        region = signal.get("region")
        sku = signal.get("sku")
        multiplier = signal.get("demand_multiplier", 1.0)

        if stype == "supply_shock":
            ff = signal.get("factory_fault", {})
            factory = ff.get("factory")
            skus = ff.get("skus", [])
            if factory and skus:
                factory_faults.setdefault(factory, [])
                for s in skus:
                    if s not in factory_faults[factory]:
                        factory_faults[factory].append(s)
            events.append(_log_event(state, "signal_received", {
                "message": f"[Market Signal] 供给冲击：{signal.get('description', '')}",
                "signal_type": stype,
            }))
        elif multiplier > 1.0 and region and sku:
            demand_shocks.setdefault(region, {})
            demand_shocks[region][sku] = max(demand_shocks[region].get(sku, 1.0), multiplier)
            events.append(_log_event(state, "signal_received", {
                "message": f"[Market Signal] 需求冲击：{signal.get('description', '')}",
                "signal_type": stype,
                "region": region,
                "sku": sku,
                "multiplier": multiplier,
            }))

    return {**state, "demand_shocks": demand_shocks, "factory_faults": factory_faults, "event_log": events}


def node_federated_forecast(state: GraphState) -> GraphState:
    """
    M3: Run federated forecast across all Sales Agents (privacy-preserving).
    Results inform shortage detection in the next node.
    """
    from graph.federated_forecast import FederatedForecastLayer
    events = list(state.get("event_log", []))
    bus = NegotiationBus()

    events.append(_log_event(state, "fed_forecast_start", {
        "message": "联邦预测层启动：各区域 Sales Agent 本地预测 + Laplace 噪声广播",
    }))

    layer = FederatedForecastLayer(bus)
    shocked_skus = list({
        sku
        for shocks in state.get("demand_shocks", {}).values()
        for sku in shocks
    }) or None

    views = layer.run(skus=shocked_skus, demand_shocks=state.get("demand_shocks", {}))

    forecast_summary: dict = {}
    for sku, view in views.items():
        forecast_summary[sku] = {
            "total_demand_72h": view.total_demand_72h,
            "by_region": view.by_region,
            "peak_region": view.peak_region,
            "shortage_risk": view.shortage_risk,
        }
        risk_regions = [r for r, at_risk in view.shortage_risk.items() if at_risk]
        if risk_regions:
            events.append(_log_event(state, "forecast_risk", {
                "message": f"[联邦预测] {sku} 72h总需求 {view.total_demand_72h:.0f} 箱，高风险区域：{', '.join(risk_regions)}",
                "sku": sku,
                "total_72h": view.total_demand_72h,
                "risk_regions": risk_regions,
            }))

    return {**state, "federated_forecasts": forecast_summary, "event_log": events}


def node_sense_demand(state: GraphState) -> GraphState:
    """Collect demand signals and compute shortage gaps."""
    log_entry = _log_event(state, "sense_demand", {
        "message": "Sales Agents 开始感知需求冲击",
        "shocks": state["demand_shocks"],
    })
    events = state.get("event_log", []) + [log_entry]

    mock_data = load_mock_data()
    live_inv = get_live_inventory()
    shortage_events = []

    for region, shocks in state["demand_shocks"].items():
        for sku, multiplier in shocks.items():
            if multiplier <= 1.0:
                continue
            # Estimate 72h demand from rolling average
            sales_records = [
                r for r in mock_data["sales"]
                if r["region"] == region and r["sku"] == sku
            ]
            if not sales_records:
                continue
            recent = sorted(sales_records, key=lambda r: r["date"])[-14:]
            avg_daily = sum(r["qty_sold"] for r in recent) / max(len(recent), 1)
            demand_72h = int(avg_daily / 24 * 72 * multiplier)

            # Current inventory across region warehouses (uses live state)
            region_whs = [w for w in WAREHOUSES if region in w]
            current_stock = sum(
                r["current_stock"]
                for r in live_inv
                if r["warehouse"] in region_whs and r["sku"] == sku
            )
            shortage = max(0, demand_72h - current_stock)
            if shortage > 0:
                shortage_events.append({
                    "sku": sku,
                    "region": region,
                    "demand_72h": demand_72h,
                    "current_stock": current_stock,
                    "shortage_qty": shortage,
                    "multiplier": multiplier,
                })
                events.append(_log_event(state, "shortage_detected", {
                    "message": f"[{region}] {sku} 预测缺口 {shortage} 箱（需求 {demand_72h} / 库存 {current_stock}）",
                    "sku": sku,
                    "region": region,
                    "shortage_qty": shortage,
                }))

    return {**state, "shortage_events": shortage_events, "event_log": events}


def node_apply_faults(state: GraphState) -> GraphState:
    """Mark factory equipment faults in the state."""
    events = list(state.get("event_log", []))
    for factory, skus in state.get("factory_faults", {}).items():
        for sku in skus:
            events.append(_log_event(state, "factory_fault", {
                "message": f"[{factory}] 设备故障，{sku} 产能下降 30%",
                "factory": factory,
                "sku": sku,
            }))
    return {**state, "event_log": events}


def node_broadcast_cfp(state: GraphState) -> GraphState:
    """Initialize all agents and broadcast CFPs for each shortage."""
    events = list(state.get("event_log", []))
    results = []

    if not state.get("shortage_events"):
        events.append(_log_event(state, "no_shortage", {"message": "未检测到缺货，协同流程跳过"}))
        return {**state, "event_log": events, "status": "done", "negotiation_results": results}

    data = load_mock_data()
    bus = NegotiationBus()

    # Instantiate agents — inventory agents use live state so stock depletes across runs
    inv_agents = [InventoryAgent(wh, bus, get_live_inventory()) for wh in WAREHOUSES]
    prod_agents = [ProductionAgent(f, bus, data["factory"]) for f in FACTORIES]

    # Apply faults
    for factory, skus in state.get("factory_faults", {}).items():
        for pa in prod_agents:
            if pa.factory == factory:
                for sku in skus:
                    pa.set_equipment_fault(sku, True)

    coordinator = CoordinatorAgent(bus)

    inv_ids = [a.agent_id for a in inv_agents]
    prod_ids = [a.agent_id for a in prod_agents]

    for shortage in state["shortage_events"]:
        sku = shortage["sku"]
        region = shortage["region"]
        qty = shortage["shortage_qty"]
        deadline = (datetime.utcnow() + timedelta(hours=48)).isoformat()

        events.append(_log_event(state, "cfp_issued", {
            "message": f"Coordinator 发起 CFP：{sku} 缺口 {qty} 箱 → {region}",
            "sku": sku,
            "region": region,
            "qty": qty,
        }))

        result: NegotiationResult = coordinator.trigger_shortage(
            sku=sku,
            required_qty=qty,
            destination_region=region,
            deadline_iso=deadline,
            inventory_agents=inv_ids,
            production_agents=prod_ids,
        )

        # Log proposal events from bus
        for msg in bus.get_log():
            if msg.performative.value == "PROPOSE" and msg.conversation_id == result.conversation_id:
                content = msg.content if isinstance(msg.content, dict) else {}
                qty_proposed = content.get("available_qty") or content.get("producible_qty", 0)
                events.append(_log_event(state, "propose_received", {
                    "message": f"{msg.sender} 投标：{qty_proposed} 箱",
                    "sender": msg.sender,
                    "qty": qty_proposed,
                    "cost": content.get("total_cost", 0),
                    "hours": content.get("transport_time_hours") or content.get("lead_time_hours", 0),
                    "reasoning": content.get("reasoning", ""),
                }))
            elif msg.performative.value == "ACCEPT":
                content = msg.content if isinstance(msg.content, dict) else {}
                events.append(_log_event(state, "accept_sent", {
                    "message": f"Coordinator → {msg.receiver}：ACCEPT {content.get('awarded_qty', 0)} 箱",
                    "receiver": msg.receiver,
                    "qty": content.get("awarded_qty", 0),
                }))

        results.append({
            "conversation_id": result.conversation_id,
            "sku": sku,
            "region": region,
            "required_qty": result.required_qty,
            "awarded_qty": result.total_awarded_qty,
            "unmet_qty": result.unmet_qty,
            "total_cost": result.total_cost,
            "stockout_loss": result.stockout_loss,
            "summary": result.summary,
            "trace": result.trace,
        })
        bus.clear()

    return {**state, "event_log": events, "negotiation_results": results}


def node_finalize(state: GraphState) -> GraphState:
    """Aggregate and log final outcome."""
    results = state.get("negotiation_results", [])
    events = list(state.get("event_log", []))

    total_cost = sum(r["total_cost"] for r in results)
    total_unmet = sum(r["unmet_qty"] for r in results)
    total_loss = sum(r["stockout_loss"] for r in results)
    total_awarded = sum(r["awarded_qty"] for r in results)

    events.append(_log_event(state, "finalized", {
        "message": (
            f"协同完成：共协调 {total_awarded} 箱，"
            f"未满足 {total_unmet} 箱，"
            f"总协同成本 ¥{total_cost:.0f}，"
            f"潜在缺货损失 ¥{total_loss:.0f}"
        ),
        "total_awarded": total_awarded,
        "total_unmet": total_unmet,
        "total_cost": total_cost,
        "stockout_loss_avoided": total_loss,
    }))
    logger.info("[graph] finalized: awarded=%d unmet=%d cost=%.0f", total_awarded, total_unmet, total_cost)
    return {**state, "event_log": events, "status": "done"}


def node_error_handler(state: GraphState) -> GraphState:
    logger.error("[graph] error: %s", state.get("error"))
    return {**state, "status": "error"}


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_negotiation_graph():
    g = StateGraph(GraphState)

    g.add_node("sense_signal", node_sense_signal)
    g.add_node("federated_forecast", node_federated_forecast)
    g.add_node("sense_demand", node_sense_demand)
    g.add_node("apply_faults", node_apply_faults)
    g.add_node("broadcast_cfp", node_broadcast_cfp)
    g.add_node("finalize", node_finalize)

    g.set_entry_point("sense_signal")
    g.add_edge("sense_signal", "federated_forecast")
    g.add_edge("federated_forecast", "sense_demand")
    g.add_edge("sense_demand", "apply_faults")
    g.add_edge("apply_faults", "broadcast_cfp")
    g.add_edge("broadcast_cfp", "finalize")
    g.add_edge("finalize", END)

    return g.compile()


# Singleton compiled graph
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_negotiation_graph()
    return _graph


def run_scenario(
    scenario_name: str,
    demand_shocks: dict[str, dict[str, float]],
    factory_faults: dict[str, list[str]] | None = None,
    market_signals: list[dict] | None = None,
    on_event=None,
) -> GraphState:
    """Stream the graph so each node's event_log increments are pushed as they occur.

    on_event: callable(event_log: list) -> None invoked after every node completion.
    """
    graph = get_graph()
    initial_state: GraphState = {
        "scenario_id": str(uuid.uuid4()),
        "scenario_name": scenario_name,
        "demand_shocks": demand_shocks,
        "factory_faults": factory_faults or {},
        "market_signals": market_signals or [],
        "federated_forecasts": {},
        "shortage_events": [],
        "negotiation_results": [],
        "event_log": [],
        "status": "running",
        "error": None,
    }
    final_state: GraphState = initial_state
    for chunk in graph.stream(initial_state, stream_mode="values"):
        final_state = chunk
        if on_event is not None:
            try:
                on_event(list(chunk.get("event_log", [])))
            except Exception:
                pass
    return final_state
