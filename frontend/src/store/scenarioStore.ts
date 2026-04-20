"use client"
import { create } from "zustand"

export type EventType =
  | "signal_received"
  | "fed_forecast_start"
  | "forecast_risk"
  | "sense_demand"
  | "shortage_detected"
  | "factory_fault"
  | "cfp_issued"
  | "propose_received"
  | "accept_sent"
  | "no_shortage"
  | "risk_assessed"
  | "finalized"
  | "stream_end"

export interface RiskItem {
  type: "shortage" | "overload" | "lead_time"
  level: "high" | "medium" | "low"
  sku: string | null
  region: string | null
  message: string
}

export interface ScenarioEvent {
  id: string
  timestamp: string
  type: EventType
  message: string
  sku?: string
  region?: string
  qty?: number
  cost?: number
  hours?: number
  reasoning?: string
  sender?: string
  receiver?: string
  multiplier?: number
  risk_regions?: string[]
  total_72h?: number
  total_awarded?: number
  total_unmet?: number
  total_cost?: number
  stockout_loss_avoided?: number
  status?: string
  risks?: RiskItem[]
  risk_count?: number
  has_high_risk?: boolean
}

export interface BidTrace {
  agent: string
  type: "inventory" | "production"
  qty: number
  cost: number
  hours: number
  score: number
  status: "ACCEPTED" | "REJECTED"
  reasoning: string
}

export interface NegotiationResult {
  conversation_id: string
  sku: string
  region: string
  required_qty: number
  awarded_qty: number
  unmet_qty: number
  total_cost: number
  stockout_loss: number
  summary: string
  trace: BidTrace[]
}

export interface ForecastView {
  total_demand_72h: number
  by_region: Record<string, number>
  peak_region: string
  shortage_risk: Record<string, boolean>
}

export interface ScenarioStore {
  runId: string | null
  status: "idle" | "running" | "done" | "error"
  selectedScenario: string
  events: ScenarioEvent[]
  negotiationResults: NegotiationResult[]
  federatedForecasts: Record<string, ForecastView>
  finalSummary: ScenarioEvent | null
  riskAssessment: RiskItem[] | null

  setSelectedScenario: (id: string) => void
  startRun: (runId: string) => void
  pushEvent: (ev: ScenarioEvent) => void
  setResults: (results: NegotiationResult[]) => void
  setForecasts: (forecasts: Record<string, ForecastView>) => void
  setStatus: (status: ScenarioStore["status"]) => void
  reset: () => void
}

export const useScenarioStore = create<ScenarioStore>((set) => ({
  runId: null,
  status: "idle",
  selectedScenario: "main",
  events: [],
  negotiationResults: [],
  federatedForecasts: {},
  finalSummary: null,
  riskAssessment: null,

  setSelectedScenario: (id) => set({ selectedScenario: id }),

  startRun: (runId) => set({ runId, status: "running", events: [], negotiationResults: [], federatedForecasts: {}, finalSummary: null }),

  pushEvent: (ev) =>
    set((s) => ({
      events: [...s.events, ev],
      finalSummary: ev.type === "finalized" ? ev : s.finalSummary,
      riskAssessment: ev.type === "risk_assessed" ? (ev.risks ?? []) : s.riskAssessment,
    })),

  setResults: (results) => set({ negotiationResults: results }),

  setForecasts: (forecasts) => set({ federatedForecasts: forecasts }),

  setStatus: (status) => set({ status }),

  reset: () => set({ runId: null, status: "idle", events: [], negotiationResults: [], federatedForecasts: {}, finalSummary: null, riskAssessment: null }),
}))
