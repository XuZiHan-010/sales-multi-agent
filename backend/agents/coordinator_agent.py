"""
Coordinator Agent — the brain of the Contract Net Protocol.

Flow per shortage event:
  1. Receive INFORM from Sales Agent (demand gap)
  2. Broadcast CFP to all Inventory + Production Agents
  3. Collect PROPOSEs within timeout
  4. Multi-objective optimization → rank bids
  5. Send ACCEPT to winners, REJECT to losers
  6. Aggregate final plan + log full negotiation trace
"""

from __future__ import annotations
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from protocols.fipa_acl import (
    ACLMessage,
    CFPContent,
    AcceptContent,
    RejectContent,
    InformContent,
    NegotiationBus,
    Performative,
    Protocol,
)
from llm.client import get_client

logger = logging.getLogger(__name__)

STOCKOUT_COST_PER_UNIT = 25.0    # ¥ per box unmet demand
BID_TIMEOUT_SEC = 2.0             # seconds to wait for proposals (in-process sim)

# Weight vector for multi-objective scoring (lower = better)
W_COST = 0.5        # total monetary cost weight
W_TIME = 0.3        # delivery time weight  (normalized to 0-1 over 72h)
W_RISK = 0.2        # supply risk weight (1 = single source, lower = diversified)


@dataclass
class BidRecord:
    msg: ACLMessage
    agent_id: str
    bid_type: str          # "inventory" | "production"
    sku: str
    qty: int
    total_cost: float
    delivery_hours: int
    reasoning: str = ""
    score: float = 0.0


@dataclass
class NegotiationResult:
    conversation_id: str
    sku: str
    required_qty: int
    destination_region: str
    awarded_bids: list[BidRecord] = field(default_factory=list)
    rejected_bids: list[BidRecord] = field(default_factory=list)
    total_awarded_qty: int = 0
    total_cost: float = 0.0
    unmet_qty: int = 0
    stockout_loss: float = 0.0
    summary: str = ""
    trace: list[dict] = field(default_factory=list)


class CoordinatorAgent:
    def __init__(self, bus: NegotiationBus):
        self.agent_id = "coordinator"
        self.bus = bus
        self.llm = get_client("coordinator")
        self._pending_cfps: dict[str, dict] = {}   # conv_id → CFP context
        self._proposals: dict[str, list[BidRecord]] = {}  # conv_id → bids
        self._results: list[NegotiationResult] = []

        bus.subscribe(self.agent_id, self._on_message)

    # ── Public API ───────────────────────────────────────────────────────────

    def trigger_shortage(
        self,
        sku: str,
        required_qty: int,
        destination_region: str,
        deadline_iso: str | None = None,
        inventory_agents: list[str] | None = None,
        production_agents: list[str] | None = None,
    ) -> NegotiationResult:
        """
        Main entry point: issue a CFP and run full Contract Net round.
        Blocks until all proposals received (synchronous simulation).
        """
        conv_id = str(uuid.uuid4())

        if deadline_iso is None:
            from datetime import datetime, timedelta
            deadline_iso = (datetime.utcnow() + timedelta(hours=48)).isoformat()

        cfp_content = CFPContent(
            sku=sku,
            required_qty=required_qty,
            deadline_iso=deadline_iso,
            destination_region=destination_region,
        )

        self._pending_cfps[conv_id] = {
            "sku": sku,
            "required_qty": required_qty,
            "destination_region": destination_region,
            "deadline_iso": deadline_iso,
            "inventory_agents": inventory_agents or [],
            "production_agents": production_agents or [],
        }
        self._proposals[conv_id] = []

        all_agents = (inventory_agents or []) + (production_agents or [])
        logger.info("[coordinator] CFP conv=%s sku=%s qty=%d agents=%s", conv_id, sku, required_qty, all_agents)

        for agent_id in all_agents:
            cfp_msg = ACLMessage(
                sender=self.agent_id,
                receiver=agent_id,
                performative=Performative.CFP,
                protocol=Protocol.CONTRACT_NET,
                content=cfp_content.model_dump(),
                conversation_id=conv_id,
            )
            self.bus.publish(cfp_msg)

        # Wait for proposals (blocking poll in synchronous simulation)
        deadline = time.monotonic() + BID_TIMEOUT_SEC
        while time.monotonic() < deadline:
            time.sleep(0.05)

        result = self._evaluate_and_award(conv_id)
        self._results.append(result)
        return result

    # ── Scoring ──────────────────────────────────────────────────────────────

    def _score_bid(self, bid: BidRecord, max_cost: float, max_time: int, bid_count: int) -> float:
        cost_norm = bid.total_cost / max(max_cost, 1)
        time_norm = bid.delivery_hours / max(max_time, 1)
        # Risk = 1 / diversity: more competing bidders → lower risk score
        risk_norm = 1.0 / max(bid_count, 1)
        # Lower score = better; weights sum to 1.0
        return W_COST * cost_norm + W_TIME * time_norm + W_RISK * risk_norm

    def _evaluate_and_award(self, conv_id: str) -> NegotiationResult:
        ctx = self._pending_cfps[conv_id]
        bids = self._proposals.get(conv_id, [])
        sku = ctx["sku"]
        required = ctx["required_qty"]
        dest = ctx["destination_region"]

        if not bids:
            logger.warning("[coordinator] No bids received for %s conv=%s", sku, conv_id)
            result = NegotiationResult(
                conversation_id=conv_id,
                sku=sku,
                required_qty=required,
                destination_region=dest,
                unmet_qty=required,
                stockout_loss=required * STOCKOUT_COST_PER_UNIT,
                summary="无有效投标，缺货风险极高。",
            )
            result.trace.append({"event": "no_bids", "sku": sku, "conv_id": conv_id})
            return result

        # Normalize for scoring
        max_cost = max(b.total_cost for b in bids)
        max_time = max(b.delivery_hours for b in bids)
        bid_count = len(bids)
        for bid in bids:
            bid.score = self._score_bid(bid, max_cost, max_time, bid_count)

        bids_sorted = sorted(bids, key=lambda b: b.score)

        awarded: list[BidRecord] = []
        rejected: list[BidRecord] = []
        remaining = required

        for bid in bids_sorted:
            if remaining <= 0:
                rejected.append(bid)
                continue
            award_qty = min(bid.qty, remaining)
            bid.qty = award_qty
            awarded.append(bid)
            remaining -= award_qty

        # Reject all non-awarded bids
        for bid in bids_sorted:
            if bid not in awarded:
                rejected.append(bid)

        total_cost = sum(b.total_cost * (b.qty / max(b.qty, 1)) for b in awarded)
        unmet = max(0, remaining)

        # Send ACCEPT / REJECT messages
        for bid in awarded:
            accept_msg = ACLMessage(
                sender=self.agent_id,
                receiver=bid.agent_id,
                performative=Performative.ACCEPT,
                protocol=Protocol.CONTRACT_NET,
                content=AcceptContent(
                    sku=sku,
                    awarded_qty=bid.qty,
                    reason=f"最优评分 {bid.score:.3f}，中标",
                ).model_dump(),
                in_reply_to=bid.msg.msg_id,
                conversation_id=conv_id,
            )
            self.bus.publish(accept_msg)
            logger.info("[coordinator] ACCEPT %s qty=%d score=%.3f", bid.agent_id, bid.qty, bid.score)

        for bid in rejected:
            reject_msg = ACLMessage(
                sender=self.agent_id,
                receiver=bid.agent_id,
                performative=Performative.REJECT,
                protocol=Protocol.CONTRACT_NET,
                content=RejectContent(sku=sku, reason="有更优投标方").model_dump(),
                in_reply_to=bid.msg.msg_id,
                conversation_id=conv_id,
            )
            self.bus.publish(reject_msg)

        summary = self._llm_summary(sku, required, awarded, unmet, dest)

        result = NegotiationResult(
            conversation_id=conv_id,
            sku=sku,
            required_qty=required,
            destination_region=dest,
            awarded_bids=awarded,
            rejected_bids=rejected,
            total_awarded_qty=required - unmet,
            total_cost=round(total_cost, 2),
            unmet_qty=unmet,
            stockout_loss=round(unmet * STOCKOUT_COST_PER_UNIT, 2),
            summary=summary,
            trace=self._build_trace(conv_id, bids_sorted, awarded),
        )
        return result

    # ── LLM Summary ──────────────────────────────────────────────────────────

    def _llm_summary(
        self,
        sku: str,
        required: int,
        awarded: list[BidRecord],
        unmet: int,
        dest: str,
    ) -> str:
        awarded_lines = "\n".join(
            f"- {b.agent_id}（{b.bid_type}）：{b.qty}箱，{b.delivery_hours}h，¥{b.total_cost:.0f}，理由：{b.reasoning[:60]}"
            for b in awarded
        )
        prompt = [
            {
                "role": "system",
                "content": (
                    "你是产销协同 Coordinator Agent，刚完成一轮 Contract Net 谈判。"
                    "请用3-4句中文总结协同结果，说明为什么选择这些供应方，以及潜在风险。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"SKU：{sku}，目标区域：{dest}，需求：{required}箱\n"
                    f"中标方案：\n{awarded_lines if awarded_lines else '无中标'}\n"
                    f"未满足量：{unmet}箱\n"
                    "请输出协同决策摘要。"
                ),
            },
        ]
        try:
            return self.llm.chat(prompt, max_tokens=300)
        except Exception:
            filled = required - unmet
            return (
                f"本轮谈判完成：{sku} 共协同 {filled}/{required} 箱至{dest}，"
                f"未满足 {unmet} 箱。"
                f"中标方：{', '.join(b.agent_id for b in awarded) or '无'}。"
            )

    # ── Trace builder ─────────────────────────────────────────────────────────

    def _build_trace(
        self,
        conv_id: str,
        all_bids: list[BidRecord],
        awarded: list[BidRecord],
    ) -> list[dict]:
        awarded_ids = {b.agent_id for b in awarded}
        trace = []
        for bid in all_bids:
            content = bid.msg.content if isinstance(bid.msg.content, dict) else {}
            entry: dict = {
                "agent": bid.agent_id,
                "type": bid.bid_type,
                "sku": bid.sku,
                "qty": bid.qty,
                "awarded_qty": bid.qty if bid.agent_id in awarded_ids else 0,
                "cost": bid.total_cost,
                "hours": bid.delivery_hours,
                "score": round(bid.score, 4),
                "status": "ACCEPTED" if bid.agent_id in awarded_ids else "REJECTED",
                "reasoning": bid.reasoning,
            }
            if bid.bid_type == "inventory":
                entry["warehouse"] = content.get("warehouse", "")
            trace.append(entry)
        return trace

    # ── Message Handler ──────────────────────────────────────────────────────

    def _on_message(self, msg: ACLMessage) -> None:
        if msg.sender == self.agent_id:
            return

        if msg.performative == Performative.PROPOSE:
            conv_id = msg.conversation_id
            if conv_id not in self._proposals:
                return

            content = msg.content if isinstance(msg.content, dict) else {}
            bid_type = "inventory" if "warehouse" in content else "production"
            qty = content.get("available_qty") or content.get("producible_qty", 0)
            hours = content.get("transport_time_hours") or content.get("lead_time_hours", 48)
            total_cost = content.get("total_cost", 0)
            reasoning = content.get("reasoning", "")

            bid = BidRecord(
                msg=msg,
                agent_id=msg.sender,
                bid_type=bid_type,
                sku=content.get("sku", ""),
                qty=qty,
                total_cost=total_cost,
                delivery_hours=hours,
                reasoning=reasoning,
            )
            self._proposals[conv_id].append(bid)
            logger.info("[coordinator] received PROPOSE from %s qty=%d cost=%.0f", msg.sender, qty, total_cost)

        elif msg.performative == Performative.INFORM:
            content = msg.content if isinstance(msg.content, dict) else {}
            logger.info("[coordinator] INFORM from %s: %s", msg.sender, content.get("message", ""))

    # ── Accessors ─────────────────────────────────────────────────────────────

    def get_results(self) -> list[NegotiationResult]:
        return list(self._results)
