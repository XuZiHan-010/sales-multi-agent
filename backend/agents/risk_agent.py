"""
Risk Agent — pure observer, no bidding.

Reads negotiation_results after broadcast_cfp and identifies:
  1. Shortage risk  — unmet_qty > 0
  2. Overload risk  — factory accepted > 80% capacity
  3. Lead-time risk — >30% of accepted orders have lead_time > 48h
"""

from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)

LEAD_TIME_THRESHOLD_H = 48
OVERLOAD_THRESHOLD = 0.8


def assess_risks(
    negotiation_results: list[dict],
    factory_capacities: dict[str, int] | None = None,
) -> list[dict]:
    """
    Returns a list of risk dicts: {type, level, sku, region, message}
    level: "high" | "medium" | "low"
    """
    risks: list[dict] = []

    factory_accepted: dict[str, int] = {}
    late_orders = 0
    total_orders = 0

    for r in negotiation_results:
        sku = r.get("sku", "")
        region = r.get("region", "")
        unmet = r.get("unmet_qty", 0)
        awarded = r.get("awarded_qty", 0)

        # 1. Shortage risk
        if unmet and unmet > 0:
            fill_rate = awarded / (awarded + unmet) if (awarded + unmet) > 0 else 0
            level = "high" if fill_rate < 0.7 else "medium"
            risks.append({
                "type": "shortage",
                "level": level,
                "sku": sku,
                "region": region,
                "message": f"{region} {sku} 缺口 {unmet:,} 箱（满足率 {fill_rate:.0%}）",
            })

        # 2 & 3. Aggregate from trace
        for bid in r.get("trace", []):
            agent = bid.get("agent", "")
            qty = bid.get("awarded_qty", 0) or 0
            hours = bid.get("lead_time_hours") or bid.get("transport_time_hours") or 0

            if qty > 0:
                total_orders += 1
                if hours > LEAD_TIME_THRESHOLD_H:
                    late_orders += 1

            if "production" in agent and qty > 0:
                # extract factory name from agent id like "production_广州厂"
                factory = agent.replace("production_", "")
                factory_accepted[factory] = factory_accepted.get(factory, 0) + qty

    # 2. Overload risk
    if factory_capacities:
        for factory, accepted in factory_accepted.items():
            cap = factory_capacities.get(factory, 0)
            if cap > 0 and accepted / cap > OVERLOAD_THRESHOLD:
                ratio = accepted / cap
                risks.append({
                    "type": "overload",
                    "level": "high" if ratio > 0.95 else "medium",
                    "sku": None,
                    "region": None,
                    "message": f"{factory} 产能负载 {ratio:.0%}，存在排产风险",
                })

    # 3. Lead-time risk
    if total_orders > 0 and late_orders / total_orders > 0.3:
        risks.append({
            "type": "lead_time",
            "level": "medium",
            "sku": None,
            "region": None,
            "message": f"{late_orders}/{total_orders} 笔订单交期 >{LEAD_TIME_THRESHOLD_H}h，建议提前排产",
        })

    logger.info("[risk_agent] assessed %d risks from %d results", len(risks), len(negotiation_results))
    return risks
