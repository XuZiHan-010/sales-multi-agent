"""
Sales Agent — one per region (华北 / 华东 / 华南).

Responsibilities:
  1. Load local sales history (never shared raw)
  2. Run Prophet forecast for next 72 h per SKU
  3. Apply Laplace noise (federated privacy simulation)
  4. Broadcast DemandForecastContent via NegotiationBus
  5. Optionally call LLM to summarise anomalies in natural language
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from protocols.fipa_acl import (
    ACLMessage,
    DemandForecastContent,
    NegotiationBus,
    Performative,
    Protocol,
)
from llm.client import get_client
from data.generate_mock_data import load_mock_data, SKUS

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

LAPLACE_SCALE = 0.03  # privacy noise level (3% of mean)


def _agent_id(region: str) -> str:
    mapping = {"华北": "sales_north", "华东": "sales_east", "华南": "sales_south"}
    return mapping.get(region, f"sales_{region}")


class SalesAgent:
    def __init__(self, region: str, bus: NegotiationBus):
        self.region = region
        self.agent_id = _agent_id(region)
        self.bus = bus
        self.llm = get_client(self.agent_id)
        self._data: dict | None = None

        bus.subscribe(self.agent_id, self._on_message)
        bus.subscribe("broadcast", self._on_message)

    # ── Data ────────────────────────────────────────────────────────────────

    def _load_data(self) -> pd.DataFrame:
        if self._data is None:
            self._data = load_mock_data()
        records = [
            r for r in self._data["sales"]
            if r["region"] == self.region
        ]
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        return df

    # ── Forecast ─────────────────────────────────────────────────────────────

    def forecast_sku(
        self,
        sku: str,
        horizon_hours: int = 72,
        shock_multiplier: float = 1.0,
        rng: np.random.Generator | None = None,
    ) -> list[dict]:
        """
        Returns hourly forecast for the next horizon_hours.
        shock_multiplier simulates demand shocks (e.g. 3.0 for live-stream event).
        Adds Laplace noise to simulate federated privacy.
        """
        if rng is None:
            rng = np.random.default_rng()

        df = self._load_data()
        sku_df = df[df["sku"] == sku][["date", "qty_sold"]].copy()
        sku_df = sku_df.rename(columns={"date": "ds", "qty_sold": "y"})

        try:
            from prophet import Prophet  # lazy import

            model = Prophet(
                daily_seasonality=True,
                weekly_seasonality=True,
                yearly_seasonality=False,
                interval_width=0.8,
                changepoint_prior_scale=0.1,
            )
            model.fit(sku_df, iter=300)

            future = model.make_future_dataframe(periods=3, freq="D")
            forecast_df = model.predict(future)
            last_3 = forecast_df.tail(3)

            daily_mean = last_3["yhat"].mean()
            daily_lower = last_3["yhat_lower"].mean()
            daily_upper = last_3["yhat_upper"].mean()

        except Exception:
            # Fallback: simple rolling mean
            daily_mean = sku_df["y"].tail(14).mean()
            daily_lower = daily_mean * 0.8
            daily_upper = daily_mean * 1.2

        hourly_base = daily_mean / 24.0
        hourly_lower = daily_lower / 24.0
        hourly_upper = daily_upper / 24.0

        result = []
        now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        for h in range(horizon_hours):
            ts = now + timedelta(hours=h)
            noise = rng.laplace(0, LAPLACE_SCALE * hourly_base)
            qty_mean = max(0.0, (hourly_base + noise) * shock_multiplier)
            result.append({
                "timestamp": ts.isoformat(),
                "qty_mean": round(qty_mean, 1),
                "qty_p10": round(max(0.0, hourly_lower * shock_multiplier), 1),
                "qty_p90": round(hourly_upper * shock_multiplier, 1),
            })
        return result

    def forecast_all_skus(
        self,
        horizon_hours: int = 72,
        shock: dict[str, float] | None = None,
    ) -> dict[str, list[dict]]:
        """Forecast all SKUs. shock = {sku: multiplier}."""
        shock = shock or {}
        return {
            sku: self.forecast_sku(sku, horizon_hours, shock.get(sku, 1.0))
            for sku in SKUS
        }

    # ── Broadcast ────────────────────────────────────────────────────────────

    def broadcast_forecast(
        self,
        horizon_hours: int = 72,
        shock: dict[str, float] | None = None,
        conversation_id: str | None = None,
    ) -> list[ACLMessage]:
        forecasts = self.forecast_all_skus(horizon_hours, shock)
        messages = []
        for sku, fc in forecasts.items():
            content = DemandForecastContent(
                region=self.region,
                sku=sku,
                forecast_horizon_hours=horizon_hours,
                forecast=fc,
                noise_applied=True,
                method="prophet",
            )
            msg = ACLMessage(
                sender=self.agent_id,
                receiver="broadcast",
                performative=Performative.INFORM,
                protocol=Protocol.FEDERATED_FORECAST,
                content=content.model_dump(),
                conversation_id=conversation_id,
            )
            self.bus.publish(msg)
            messages.append(msg)
            logger.info("[%s] broadcast forecast for %s | horizon=%dh", self.agent_id, sku, horizon_hours)
        return messages

    # ── LLM Anomaly Summary ──────────────────────────────────────────────────

    def summarise_anomalies(self, shock: dict[str, float]) -> str:
        shocked_skus = [f"{sku}(×{v})" for sku, v in shock.items() if v != 1.0]
        if not shocked_skus:
            return f"[{self.region}] 当前无需求冲击，预测正常。"

        prompt = [
            {
                "role": "system",
                "content": (
                    "你是一个快消品销售分析师 Agent，负责华南大区。"
                    "请用2-3句中文总结以下需求异常，指出风险和建议。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"大区：{self.region}\n"
                    f"以下SKU出现需求冲击：{', '.join(shocked_skus)}\n"
                    "请简要分析风险并建议库存补货优先级。"
                ),
            },
        ]
        try:
            return self.llm.chat(prompt, max_tokens=300)
        except Exception as e:
            return f"[LLM unavailable] Shock detected: {', '.join(shocked_skus)}"

    # ── Message Handler ──────────────────────────────────────────────────────

    def _on_message(self, msg: ACLMessage) -> None:
        if msg.sender == self.agent_id:
            return
        if msg.performative == Performative.REQUEST and isinstance(msg.content, dict):
            action = msg.content.get("action")
            if action == "forecast":
                shock = msg.content.get("shock", {})
                self.broadcast_forecast(shock=shock, conversation_id=msg.conversation_id)
