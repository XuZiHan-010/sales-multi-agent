"""
Production Agent — one per factory (天津厂 / 上海厂 / 广州厂).

Responsibilities:
  1. Track capacity, utilization, switch cost, equipment status
  2. Evaluate CFP from Coordinator
  3. PROPOSE with (producible_qty, lead_time, marginal_cost, switch_cost, total_cost)
  4. Execute ACCEPT → update utilization (simulate)
"""

from __future__ import annotations
import logging

from protocols.fipa_acl import (
    ACLMessage,
    CFPContent,
    ProductionBidContent,
    InformContent,
    AcceptContent,
    RejectContent,
    NegotiationBus,
    Performative,
)
from llm.client import get_client
from data.generate_mock_data import FACTORY_CAPACITY

logger = logging.getLogger(__name__)

# Approximate lead times (hours) from factory to closest destination warehouse
FACTORY_LEAD_TIMES: dict[str, dict[str, int]] = {
    "天津厂": {"华北": 6,  "华东": 20, "华南": 38},
    "上海厂": {"华北": 20, "华东": 4,  "华南": 17},
    "广州厂": {"华北": 38, "华东": 17, "华南": 4},
}

MARGINAL_COST_PER_UNIT: dict[str, float] = {
    "天津厂": 8.5,
    "上海厂": 9.2,
    "广州厂": 8.8,
}


class ProductionAgent:
    def __init__(self, factory: str, bus: NegotiationBus, factory_data: list[dict]):
        self.factory = factory
        self.agent_id = f"production_{factory.replace('厂', '').replace('津', 'tj').replace('海', 'sh').replace('州', 'gz')}"
        self.bus = bus
        self.llm = get_client("production")

        # Build local capacity map: {sku: {...}}
        self._capacity: dict[str, dict] = {}
        for row in factory_data:
            if row["factory"] == factory:
                self._capacity[row["sku"]] = {
                    "max_capacity_monthly": row["max_capacity_monthly"],
                    "current_utilization": row["current_utilization"],
                    "available_capacity": row["available_capacity"],
                    "switch_cost_per_batch": row["switch_cost_per_batch"],
                    "equipment_ok": row["equipment_ok"],
                }

        bus.subscribe(self.agent_id, self._on_message)

    # ── Capacity helpers ─────────────────────────────────────────────────────

    def available_capacity(self, sku: str) -> int:
        c = self._capacity.get(sku, {})
        return c.get("available_capacity", 0)

    def _lead_time(self, destination_region: str) -> int:
        lt = FACTORY_LEAD_TIMES.get(self.factory, {})
        return lt.get(destination_region, 24)

    # ── Bidding logic ─────────────────────────────────────────────────────────

    def evaluate_cfp(self, cfp: CFPContent) -> ProductionBidContent | None:
        avail = self.available_capacity(cfp.sku)
        if avail <= 0:
            return None

        offer_qty = min(avail, cfp.required_qty)
        marginal = MARGINAL_COST_PER_UNIT.get(self.factory, 9.0)
        switch = self._capacity.get(cfp.sku, {}).get("switch_cost_per_batch", 10000)
        lead = self._lead_time(cfp.destination_region)
        total = round(offer_qty * marginal + switch, 2)

        return ProductionBidContent(
            factory=self.factory,
            sku=cfp.sku,
            producible_qty=offer_qty,
            lead_time_hours=lead,
            marginal_cost_per_unit=marginal,
            switch_cost=switch,
            total_cost=total,
        )

    def _llm_reasoning(self, cfp: CFPContent, bid: ProductionBidContent) -> str:
        util = self._capacity.get(cfp.sku, {}).get("current_utilization", 0)
        prompt = [
            {
                "role": "system",
                "content": "你是一个工厂生产排程 Agent。请用1-2句中文说明投标决策理由。",
            },
            {
                "role": "user",
                "content": (
                    f"工厂：{self.factory}，当前产能利用率：{util:.0%}\n"
                    f"SKU：{cfp.sku}，需求：{cfp.required_qty}箱\n"
                    f"可补产：{bid.producible_qty}箱，交货期：{bid.lead_time_hours}h\n"
                    f"边际成本：¥{bid.marginal_cost_per_unit}/箱，切换成本：¥{bid.switch_cost}\n"
                    "请简要说明投标理由，说明为什么本厂有竞争优势。"
                ),
            },
        ]
        try:
            return self.llm.chat(prompt, max_tokens=150)
        except Exception:
            return f"{self.factory}可补产{bid.producible_qty}箱，交期{bid.lead_time_hours}h，总成本¥{bid.total_cost:.0f}。"

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
                    content=RejectContent(sku=cfp.sku, reason="产能不足或设备故障").model_dump(),
                )
                logger.info("[%s] REJECT CFP for %s", self.agent_id, cfp.sku)
            else:
                reasoning = self._llm_reasoning(cfp, bid)
                content = bid.model_dump()
                content["reasoning"] = reasoning
                reply = msg.reply(
                    sender=self.agent_id,
                    performative=Performative.PROPOSE,
                    content=content,
                )
                logger.info("[%s] PROPOSE %d boxes of %s, lead=%dh", self.agent_id, bid.producible_qty, cfp.sku, bid.lead_time_hours)

            self.bus.publish(reply)

        elif msg.performative == Performative.ACCEPT:
            content = AcceptContent(**msg.content) if isinstance(msg.content, dict) else msg.content
            # Update available capacity
            if content.sku in self._capacity:
                cap = self._capacity[content.sku]
                cap["available_capacity"] = max(0, cap["available_capacity"] - content.awarded_qty)
                new_util = 1.0 - cap["available_capacity"] / max(1, cap["max_capacity_monthly"])
                cap["current_utilization"] = round(new_util, 3)

            confirm = msg.reply(
                sender=self.agent_id,
                performative=Performative.INFORM,
                content=InformContent(
                    status="executing",
                    message=f"{self.factory} 已接受排产任务：{content.awarded_qty} 箱 {content.sku}",
                    payload={"factory": self.factory, "sku": content.sku, "qty": content.awarded_qty},
                ).model_dump(),
            )
            self.bus.publish(confirm)
            logger.info("[%s] ACCEPT confirmed, capacity updated", self.agent_id)

        elif msg.performative == Performative.REJECT:
            logger.info("[%s] production bid rejected", self.agent_id)

    def set_equipment_fault(self, sku: str, fault: bool) -> None:
        if sku in self._capacity:
            if fault:
                self._capacity[sku]["available_capacity"] = int(
                    self._capacity[sku]["available_capacity"] * 0.7
                )
            logger.info("[%s] equipment fault=%s for %s, available_capacity=%d", self.agent_id, fault, sku, self._capacity[sku]["available_capacity"])
