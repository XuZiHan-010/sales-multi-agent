"""
Market Signal Agent — monitors external signals and pushes demand/supply shocks.

Signal sources:
  1. Mock event injection (always available, used for demo)
  2. Exa search API (real-time web search, requires EXA_API_KEY)

Output: MarketSignalContent broadcast → Coordinator reacts
"""

from __future__ import annotations
import logging
import os
from datetime import datetime
from typing import Any

from protocols.fipa_acl import (
    ACLMessage,
    MarketSignalContent,
    NegotiationBus,
    Performative,
    Protocol,
)
from llm.client import get_client

logger = logging.getLogger(__name__)

# ── Built-in mock event library ───────────────────────────────────────────────

MOCK_EVENTS: dict[str, dict] = {
    "livestream_sku_a": {
        "signal_type": "livestream",
        "region": "华南",
        "sku": "SKU-A",
        "demand_multiplier": 3.0,
        "duration_hours": 48,
        "description": "头部主播直播带货 SKU-A，预计带动华南区需求激增 3 倍",
        "source": "mock_livestream_calendar",
    },
    "competitor_promo": {
        "signal_type": "competitor",
        "region": None,
        "sku": "SKU-B",
        "demand_multiplier": 1.8,
        "duration_hours": 72,
        "description": "竞品 X 促销活动结束，本品 SKU-B 预计承接溢出需求",
        "source": "mock_competitor_monitor",
    },
    "south_heatwave": {
        "signal_type": "weather",
        "region": "华南",
        "sku": None,
        "demand_multiplier": 1.4,
        "duration_hours": 96,
        "description": "华南地区高温预警（>38°C），功能饮料需求预计上涨 40%",
        "source": "mock_weather_api",
    },
    "factory_fault_gz": {
        "signal_type": "supply_shock",
        "region": None,
        "sku": "SKU-A",
        "demand_multiplier": 1.0,
        "duration_hours": 24,
        "description": "广州厂 SKU-A 产线设备故障，产能下降 30%",
        "source": "mock_iot_monitor",
        "factory_fault": {"factory": "广州厂", "skus": ["SKU-A"]},
    },
}


class MarketSignalAgent:
    def __init__(self, bus: NegotiationBus):
        self.agent_id = "market_signal"
        self.bus = bus
        self.llm = get_client("market_signal")
        self._exa_key = os.getenv("EXA_API_KEY", "")
        bus.subscribe(self.agent_id, self._on_message)

    # ── Mock event injection ─────────────────────────────────────────────────

    def inject_mock_event(self, event_key: str) -> ACLMessage | None:
        event = MOCK_EVENTS.get(event_key)
        if not event:
            logger.warning("[market_signal] Unknown event key: %s", event_key)
            return None
        return self._publish_signal(event)

    def inject_custom_event(self, signal_data: dict) -> ACLMessage:
        return self._publish_signal(signal_data)

    def _publish_signal(self, data: dict) -> ACLMessage:
        content = MarketSignalContent(
            signal_type=data["signal_type"],
            region=data.get("region"),
            sku=data.get("sku"),
            demand_multiplier=data.get("demand_multiplier", 1.0),
            duration_hours=data.get("duration_hours", 48),
            description=data.get("description", ""),
            source=data.get("source", "market_signal"),
        )
        # Attach factory fault info if present (non-schema extra payload)
        content_dict = content.model_dump()
        if "factory_fault" in data:
            content_dict["factory_fault"] = data["factory_fault"]

        msg = ACLMessage(
            sender=self.agent_id,
            receiver="coordinator",
            performative=Performative.INFORM,
            protocol=Protocol.MARKET_SIGNAL,
            content=content_dict,
        )
        self.bus.publish(msg)
        logger.info(
            "[market_signal] signal published: %s | sku=%s | region=%s | ×%.1f",
            data["signal_type"], data.get("sku"), data.get("region"), data.get("demand_multiplier", 1.0),
        )
        return msg

    # ── Exa real-time search ─────────────────────────────────────────────────

    def search_and_signal(self, query: str, sku: str | None = None, region: str | None = None) -> ACLMessage | None:
        """Search web via Exa API and publish a signal if demand impact found."""
        if not self._exa_key:
            logger.warning("[market_signal] EXA_API_KEY not set, skipping web search")
            return None

        raw_results = self._exa_search(query)
        if not raw_results:
            return None

        analysis = self._llm_analyse(query, raw_results, sku, region)
        if not analysis.get("has_impact"):
            logger.info("[market_signal] Exa search: no demand impact detected")
            return None

        return self._publish_signal({
            "signal_type": analysis.get("signal_type", "news"),
            "region": analysis.get("region", region),
            "sku": analysis.get("sku", sku),
            "demand_multiplier": analysis.get("demand_multiplier", 1.1),
            "duration_hours": analysis.get("duration_hours", 48),
            "description": analysis.get("description", raw_results[:200]),
            "source": f"exa:{query[:40]}",
        })

    def _exa_search(self, query: str) -> str:
        try:
            import httpx
            resp = httpx.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": self._exa_key, "Content-Type": "application/json"},
                json={
                    "query": query,
                    "numResults": 3,
                    "contents": {"text": {"maxCharacters": 500}},
                },
                timeout=10,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            return "\n".join(r.get("text", "") for r in results if r.get("text"))
        except Exception as e:
            logger.warning("[market_signal] Exa search failed: %s", e)
            return ""

    def _llm_analyse(
        self, query: str, raw_text: str, sku: str | None, region: str | None
    ) -> dict:
        prompt = [
            {
                "role": "system",
                "content": (
                    "你是快消品市场信号分析师。根据搜索结果判断是否有需求冲击，"
                    "输出JSON格式：{has_impact, signal_type, region, sku, demand_multiplier, duration_hours, description}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"搜索关键词：{query}\n"
                    f"参考SKU：{sku or '不限'}，参考区域：{region or '不限'}\n"
                    f"搜索结果：\n{raw_text[:800]}\n"
                    "请判断是否存在需求冲击并输出JSON。demand_multiplier 范围 1.0-5.0，无冲击时 has_impact=false。"
                ),
            },
        ]
        try:
            import json
            raw = self.llm.chat_json(prompt, max_tokens=300)
            return json.loads(raw)
        except Exception:
            return {"has_impact": False}

    # ── Message handler ──────────────────────────────────────────────────────

    def _on_message(self, msg: ACLMessage) -> None:
        pass  # Market Signal Agent only publishes; no inbound handling needed
