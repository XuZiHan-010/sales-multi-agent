"""
Inventory Agent — one per warehouse.

Responsibilities:
  1. Track current stock, safety stock, in-transit
  2. Evaluate CFP from Coordinator
  3. Generate PROPOSE with (available_qty, transport_cost, transport_time, total_cost)
  4. Execute ACCEPT → update stock (simulate)
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from protocols.fipa_acl import (
    ACLMessage,
    CFPContent,
    InventoryBidContent,
    InformContent,
    AcceptContent,
    RejectContent,
    NegotiationBus,
    Performative,
    Protocol,
)
from llm.client import get_client
from data.generate_mock_data import WAREHOUSES

logger = logging.getLogger(__name__)

REGION_TO_WAREHOUSES: dict[str, list[str]] = {
    "华北": ["华北-仓1", "华北-仓2", "华北-仓3"],
    "华东": ["华东-仓1", "华东-仓2", "华东-仓3"],
    "华南": ["华南-仓1", "华南-仓2", "华南-仓3"],
    "全国": ["中转-仓1"],
}

# Warehouse → region mapping for cost lookup
_WH_REGION: dict[str, str] = {
    **{w: "华北" for w in ["华北-仓1", "华北-仓2", "华北-仓3"]},
    **{w: "华东" for w in ["华东-仓1", "华东-仓2", "华东-仓3"]},
    **{w: "华南" for w in ["华南-仓1", "华南-仓2", "华南-仓3"]},
    "中转-仓1": None,
}

# Region-to-region transport cost (¥/box) and time (hours)
_REGION_COST: dict[tuple[str, str], float] = {
    ("华北", "华北"): 60,  ("华北", "华东"): 125, ("华北", "华南"): 205,
    ("华东", "华北"): 125, ("华东", "华东"): 50,  ("华东", "华南"): 115,
    ("华南", "华北"): 205, ("华南", "华东"): 115, ("华南", "华南"): 45,
}

_REGION_TIME: dict[tuple[str, str], int] = {
    ("华北", "华北"): 6,  ("华北", "华东"): 18, ("华北", "华南"): 36,
    ("华东", "华北"): 18, ("华东", "华东"): 4,  ("华东", "华南"): 16,
    ("华南", "华北"): 36, ("华南", "华东"): 16, ("华南", "华南"): 4,
}


class InventoryAgent:
    def __init__(self, warehouse: str, bus: NegotiationBus, inventory_data: list[dict]):
        self.warehouse = warehouse
        self.agent_id = f"inventory_{warehouse.replace('-', '_').replace('仓', 'wh')}"
        self.bus = bus
        self.llm = get_client("inventory")

        # Build local stock map: {sku: {current_stock, safety_stock, in_transit}}
        self._stock: dict[str, dict] = {}
        for row in inventory_data:
            if row["warehouse"] == warehouse:
                self._stock[row["sku"]] = {
                    "current_stock": row["current_stock"],
                    "safety_stock": row["safety_stock"],
                    "in_transit": row["in_transit"],
                }

        bus.subscribe(self.agent_id, self._on_message)

    # ── Stock helpers ────────────────────────────────────────────────────────

    def available_qty(self, sku: str) -> int:
        s = self._stock.get(sku, {})
        current = s.get("current_stock", 0)
        safety = s.get("safety_stock", 0)
        return max(0, current - safety)

    def _transport_cost(self, destination_region: str) -> float:
        src_region = _WH_REGION.get(self.warehouse)
        if src_region is None:
            return 100.0
        return _REGION_COST.get((src_region, destination_region), 150.0)

    def _transport_time(self, destination_region: str) -> int:
        src_region = _WH_REGION.get(self.warehouse)
        if src_region is None:
            return 12
        return _REGION_TIME.get((src_region, destination_region), 24)

    # ── Bidding logic ─────────────────────────────────────────────────────────

    def evaluate_cfp(self, cfp: CFPContent) -> InventoryBidContent | None:
        avail = self.available_qty(cfp.sku)
        if avail <= 0:
            return None

        offer_qty = min(avail, cfp.required_qty)
        cost_per_unit = self._transport_cost(cfp.destination_region)
        time_h = self._transport_time(cfp.destination_region)
        total = round(offer_qty * cost_per_unit, 2)

        return InventoryBidContent(
            warehouse=self.warehouse,
            sku=cfp.sku,
            available_qty=offer_qty,
            destination=cfp.destination_region,
            transport_cost=cost_per_unit,
            transport_time_hours=time_h,
            total_cost=total,
        )

    def _llm_reasoning(self, cfp: CFPContent, bid: InventoryBidContent) -> str:
        prompt = [
            {
                "role": "system",
                "content": "你是一个仓库库存管理 Agent。请用1-2句中文说明你的投标决策理由。",
            },
            {
                "role": "user",
                "content": (
                    f"仓库：{self.warehouse}\n"
                    f"SKU：{cfp.sku}，需求：{cfp.required_qty}箱\n"
                    f"我的可用库存：{bid.available_qty}箱\n"
                    f"运输到{cfp.destination_region}：{bid.transport_time_hours}h，成本¥{bid.transport_cost}/箱\n"
                    "请简要说明投标理由。"
                ),
            },
        ]
        try:
            return self.llm.chat(prompt, max_tokens=150)
        except Exception:
            return f"仓库{self.warehouse}可调拨{bid.available_qty}箱，运输时效{bid.transport_time_hours}h。"

    # ── Message Handler ──────────────────────────────────────────────────────

    def _on_message(self, msg: ACLMessage) -> None:
        if msg.sender == self.agent_id:
            return

        if msg.performative == Performative.CFP:
            cfp = CFPContent(**msg.content) if isinstance(msg.content, dict) else msg.content
            bid = self.evaluate_cfp(cfp)

            if bid is None:
                reply = msg.reply(
                    sender=self.agent_id,
                    performative=Performative.REJECT,
                    content=RejectContent(sku=cfp.sku, reason="库存不足，无法投标").model_dump(),
                )
                logger.info("[%s] REJECT CFP for %s (no stock)", self.agent_id, cfp.sku)
            else:
                reasoning = self._llm_reasoning(cfp, bid)
                content = bid.model_dump()
                content["reasoning"] = reasoning
                reply = msg.reply(
                    sender=self.agent_id,
                    performative=Performative.PROPOSE,
                    content=content,
                )
                logger.info("[%s] PROPOSE %d boxes of %s to %s", self.agent_id, bid.available_qty, cfp.sku, cfp.destination_region)

            self.bus.publish(reply)

        elif msg.performative == Performative.ACCEPT:
            content = AcceptContent(**msg.content) if isinstance(msg.content, dict) else msg.content
            # Deduct stock
            if content.sku in self._stock:
                self._stock[content.sku]["current_stock"] = max(
                    0, self._stock[content.sku]["current_stock"] - content.awarded_qty
                )
            confirm = msg.reply(
                sender=self.agent_id,
                performative=Performative.INFORM,
                content=InformContent(
                    status="executing",
                    message=f"{self.warehouse} 已确认调拨 {content.awarded_qty} 箱 {content.sku}",
                    payload={"warehouse": self.warehouse, "sku": content.sku, "qty": content.awarded_qty},
                ).model_dump(),
            )
            self.bus.publish(confirm)
            logger.info("[%s] ACCEPT confirmed, stock updated", self.agent_id)

        elif msg.performative == Performative.REJECT:
            logger.info("[%s] bid rejected by coordinator", self.agent_id)
