import type { ScenarioEvent } from "@/store/scenarioStore"

// Map an event to the agent node(s) that should react to it.
export function agentsForEvent(ev: ScenarioEvent): string[] {
  switch (ev.type) {
    case "signal_received":
      return ["market_signal"]
    case "fed_forecast_start":
    case "forecast_risk":
      return ["sales_north", "sales_east", "sales_south"]
    case "sense_demand":
    case "shortage_detected": {
      const regionAgent =
        ev.region === "华北" ? "sales_north" :
        ev.region === "华东" ? "sales_east" :
        "sales_south"
      return [regionAgent, "coordinator"]
    }
    case "factory_fault":
      return ["prod"]
    case "cfp_issued":
      return ["coordinator"]
    case "propose_received":
      if (ev.sender?.includes("inventory")) return ["inv", "coordinator"]
      if (ev.sender?.includes("production")) return ["prod", "coordinator"]
      return ["coordinator"]
    case "accept_sent":
      if (ev.receiver?.includes("inventory")) return ["inv", "coordinator"]
      if (ev.receiver?.includes("production")) return ["prod", "coordinator"]
      return ["coordinator"]
    case "no_shortage":
    case "finalized":
      return ["coordinator"]
    default:
      return []
  }
}

// Map an event to the edge direction (for animated text along lines).
// Returns {edgeId, reverse} — reverse=true means the token flows from "to" to "from".
export function edgeForEvent(ev: ScenarioEvent): { edgeId: string; reverse: boolean; label: string; color: string } | null {
  switch (ev.type) {
    case "signal_received":
      return { edgeId: "ms-co", reverse: false, label: "📡 信号", color: "#a78bfa" }
    case "fed_forecast_start":
      return { edgeId: "co-se", reverse: true, label: "预测启动", color: "#67e8f9" }
    case "cfp_issued": {
      const edgeId = Math.random() < 0.5 ? "co-inv" : "co-prd"
      return { edgeId, reverse: false, label: "📢 CFP", color: "#a5b4fc" }
    }
    case "propose_received": {
      const isInv = ev.sender?.includes("inventory")
      const edgeId = isInv ? "co-inv" : "co-prd"
      const label = ev.qty && ev.cost
        ? `${ev.qty.toLocaleString()}箱·¥${Math.round(ev.cost/1000)}K`
        : "💬 投标"
      return { edgeId, reverse: true, label, color: "#6ee7b7" }
    }
    case "accept_sent": {
      const isInv = ev.receiver?.includes("inventory")
      const edgeId = isInv ? "co-inv" : "co-prd"
      return { edgeId, reverse: false, label: "✅ 中标", color: "#4ade80" }
    }
    default:
      return null
  }
}

// Per-event short label for node-side bubbles (<=16 chars recommended)
export function bubbleLabel(ev: ScenarioEvent): string {
  if (ev.message && ev.message.length <= 28) return ev.message
  switch (ev.type) {
    case "signal_received":    return `📡 ${ev.sku ?? "信号"} ×${ev.multiplier ?? ""}`
    case "fed_forecast_start": return "🔬 开始预测"
    case "forecast_risk":      return `⚠️ ${ev.sku ?? ""} 风险`
    case "sense_demand":       return "🔍 感知需求"
    case "shortage_detected":  return `🚨 ${ev.sku ?? ""} 缺货`
    case "factory_fault":      return "🔧 产能下降"
    case "cfp_issued":         return `📢 招标 ${ev.sku ?? ""}`
    case "propose_received":   return ev.qty ? `💬 报 ${ev.qty.toLocaleString()}箱` : "💬 收到投标"
    case "accept_sent":        return ev.qty ? `✅ 中标 ${ev.qty.toLocaleString()}箱` : "✅ 中标"
    case "no_shortage":        return "✅ 无需协同"
    case "finalized":          return "🏁 协同完成"
    default:                    return ev.type
  }
}
