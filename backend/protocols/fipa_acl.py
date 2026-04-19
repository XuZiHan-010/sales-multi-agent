"""
Simplified FIPA-ACL message schema for Agent-to-Agent negotiation.
Performatives: CFP, PROPOSE, ACCEPT, REJECT, INFORM, REQUEST, FAILURE
"""

from __future__ import annotations
from enum import Enum
from typing import Any
from datetime import datetime
import uuid

from pydantic import BaseModel, Field


class Performative(str, Enum):
    CFP = "CFP"          # Call for Proposal — Coordinator → Agents
    PROPOSE = "PROPOSE"  # Bid/offer — Agent → Coordinator
    ACCEPT = "ACCEPT"    # Accept bid — Coordinator → Agent
    REJECT = "REJECT"    # Reject bid — Coordinator → Agent
    INFORM = "INFORM"    # Status notification — any direction
    REQUEST = "REQUEST"  # Trigger action — Coordinator → Agent
    FAILURE = "FAILURE"  # Error report — any direction


class Protocol(str, Enum):
    CONTRACT_NET = "contract-net"
    FEDERATED_FORECAST = "federated-forecast"
    MARKET_SIGNAL = "market-signal"


class AgentRole(str, Enum):
    COORDINATOR = "coordinator"
    SALES_NORTH = "sales_north"
    SALES_EAST = "sales_east"
    SALES_SOUTH = "sales_south"
    INVENTORY = "inventory"       # prefix with warehouse id
    PRODUCTION = "production"     # prefix with factory id
    MARKET_SIGNAL = "market_signal"


# ── Content payload schemas ──────────────────────────────────────────────────

class DemandForecastContent(BaseModel):
    region: str
    sku: str
    forecast_horizon_hours: int = 72
    forecast: list[dict]   # [{timestamp, qty_mean, qty_p10, qty_p90}]
    noise_applied: bool = True
    method: str = "prophet"


class InventoryBidContent(BaseModel):
    warehouse: str
    sku: str
    available_qty: int
    destination: str
    transport_cost: float
    transport_time_hours: int
    total_cost: float


class ProductionBidContent(BaseModel):
    factory: str
    sku: str
    producible_qty: int
    lead_time_hours: int
    marginal_cost_per_unit: float
    switch_cost: float
    total_cost: float


class CFPContent(BaseModel):
    sku: str
    required_qty: int
    deadline_iso: str
    destination_region: str
    constraints: dict[str, Any] = Field(default_factory=dict)


class AcceptContent(BaseModel):
    sku: str
    awarded_qty: int
    reason: str = ""


class RejectContent(BaseModel):
    sku: str
    reason: str = ""


class MarketSignalContent(BaseModel):
    signal_type: str   # "livestream" | "weather" | "competitor" | "holiday"
    region: str | None = None
    sku: str | None = None
    demand_multiplier: float = 1.0
    duration_hours: int = 48
    description: str = ""
    source: str = ""


class InformContent(BaseModel):
    status: str
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


# ── Core Message ─────────────────────────────────────────────────────────────

ContentType = (
    DemandForecastContent
    | InventoryBidContent
    | ProductionBidContent
    | CFPContent
    | AcceptContent
    | RejectContent
    | MarketSignalContent
    | InformContent
    | dict
)


class ACLMessage(BaseModel):
    msg_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: str
    receiver: str  # agent id or "broadcast"
    performative: Performative
    protocol: Protocol = Protocol.CONTRACT_NET
    content: Any
    in_reply_to: str | None = None
    conversation_id: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    def reply(
        self,
        sender: str,
        performative: Performative,
        content: Any,
    ) -> "ACLMessage":
        return ACLMessage(
            sender=sender,
            receiver=self.sender,
            performative=performative,
            protocol=self.protocol,
            content=content,
            in_reply_to=self.msg_id,
            conversation_id=self.conversation_id or self.msg_id,
        )


# ── Message Bus (in-memory) ───────────────────────────────────────────────────

class NegotiationBus:
    """Simple in-memory publish/subscribe bus for agent messages."""

    def __init__(self):
        self._log: list[ACLMessage] = []
        self._subscribers: dict[str, list] = {}  # agent_id → list[callback]

    def publish(self, msg: ACLMessage) -> None:
        self._log.append(msg)
        targets = (
            list(self._subscribers.keys())
            if msg.receiver == "broadcast"
            else [msg.receiver]
        )
        for target in targets:
            for cb in self._subscribers.get(target, []):
                cb(msg)

    def subscribe(self, agent_id: str, callback) -> None:
        self._subscribers.setdefault(agent_id, []).append(callback)

    def get_log(self) -> list[ACLMessage]:
        return list(self._log)

    def get_conversation(self, conversation_id: str) -> list[ACLMessage]:
        return [m for m in self._log if m.conversation_id == conversation_id]

    def clear(self) -> None:
        self._log.clear()
        # Intentionally keep _subscribers so agents remain active across multiple shortage rounds
