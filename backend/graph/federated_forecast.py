"""
Federated Forecast Layer.

Privacy model:
  - Each Sales Agent forecasts locally (raw data never leaves the region)
  - Results are perturbed with Laplace noise before broadcast
  - Coordinator aggregates noisy forecasts into a global demand view

This is a simplified simulation of federated learning:
  real FL would exchange gradients; here we exchange noisy predictions.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field

import numpy as np

from protocols.fipa_acl import NegotiationBus
from agents.sales_agent import SalesAgent
from data.generate_mock_data import REGIONS, SKUS

logger = logging.getLogger(__name__)


@dataclass
class RegionalForecast:
    region: str
    sku: str
    horizon_hours: int
    forecast: list[dict]       # [{timestamp, qty_mean, qty_p10, qty_p90}]
    noise_scale: float         # Laplace noise scale applied
    shock_multiplier: float    # demand shock applied


@dataclass
class GlobalDemandView:
    """Aggregated forecast across all regions."""
    sku: str
    horizon_hours: int
    total_demand_72h: float
    by_region: dict[str, float]         # region → total 72h demand
    peak_region: str
    shortage_risk: dict[str, bool]      # region → True if likely shortage
    regional_forecasts: list[RegionalForecast] = field(default_factory=list)


class FederatedForecastLayer:
    """
    Coordinates Sales Agents to produce a privacy-preserving global demand view.
    """

    def __init__(self, bus: NegotiationBus):
        self.bus = bus
        self._agents: dict[str, SalesAgent] = {
            region: SalesAgent(region, bus)
            for region in REGIONS
        }

    def run(
        self,
        skus: list[str] | None = None,
        horizon_hours: int = 72,
        demand_shocks: dict[str, dict[str, float]] | None = None,
    ) -> dict[str, GlobalDemandView]:
        """
        Run federated forecast for all SKUs across all regions.

        demand_shocks: {region: {sku: multiplier}}
        Returns: {sku: GlobalDemandView}
        """
        skus = skus or SKUS
        demand_shocks = demand_shocks or {}
        views: dict[str, GlobalDemandView] = {}

        for sku in skus:
            regional: list[RegionalForecast] = []

            for region, agent in self._agents.items():
                shock = demand_shocks.get(region, {}).get(sku, 1.0)
                forecast = agent.forecast_sku(sku, horizon_hours, shock_multiplier=shock)

                total_72h = sum(row["qty_mean"] for row in forecast)
                regional.append(RegionalForecast(
                    region=region,
                    sku=sku,
                    horizon_hours=horizon_hours,
                    forecast=forecast,
                    noise_scale=0.03,
                    shock_multiplier=shock,
                ))

            total = sum(sum(r["qty_mean"] for r in rf.forecast) for rf in regional)
            by_region = {
                rf.region: round(sum(r["qty_mean"] for r in rf.forecast), 1)
                for rf in regional
            }
            peak_region = max(by_region, key=lambda r: by_region[r])

            views[sku] = GlobalDemandView(
                sku=sku,
                horizon_hours=horizon_hours,
                total_demand_72h=round(total, 1),
                by_region=by_region,
                peak_region=peak_region,
                shortage_risk=self._assess_shortage_risk(sku, by_region),
                regional_forecasts=regional,
            )
            logger.info(
                "[fed_forecast] %s total_72h=%.0f peak_region=%s",
                sku, total, peak_region,
            )

        return views

    def _assess_shortage_risk(self, sku: str, demand_by_region: dict[str, float]) -> dict[str, bool]:
        from data.generate_mock_data import WAREHOUSES
        from data.inventory_state import get_live_inventory
        inventory = get_live_inventory()

        risk = {}
        for region in REGIONS:
            region_whs = [w for w in WAREHOUSES if region in w]
            current_stock = sum(
                r["current_stock"]
                for r in inventory
                if r["warehouse"] in region_whs and r["sku"] == sku
            )
            demand = demand_by_region.get(region, 0)
            risk[region] = demand > current_stock * 0.8   # >80% of stock = at risk
        return risk
