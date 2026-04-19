"use client"
import { useScenarioStore } from "@/store/scenarioStore"
import { useMemo } from "react"
import { agentsForEvent } from "@/lib/agentEventMap"

const AGENTS = [
  { id: "market_signal",  label: "Market Signal",  color: "bg-purple-500" },
  { id: "sales_north",    label: "Sales 华北",     color: "bg-cyan-500" },
  { id: "sales_east",     label: "Sales 华东",     color: "bg-cyan-500" },
  { id: "sales_south",    label: "Sales 华南",     color: "bg-cyan-500" },
  { id: "inv",            label: "Inventory ×10",  color: "bg-amber-500" },
  { id: "prod",           label: "Production ×3",  color: "bg-rose-500" },
  { id: "coordinator",    label: "Coordinator",    color: "bg-indigo-500" },
]

export default function AgentStatusPanel() {
  const { events, status } = useScenarioStore()

  const activeAgents = useMemo(() => {
    const s = new Set<string>()
    events.forEach((ev) => agentsForEvent(ev).forEach((id) => s.add(id)))
    return s
  }, [events])

  return (
    <div className="rounded-xl border border-indigo-500/20 bg-[#1a1d2e]/80 p-3 shrink-0">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-slate-300">Agent 协同网络</h2>
        <span className="text-[11px] text-slate-600">7 节点</span>
      </div>
      <div className="flex flex-col gap-0.5 overflow-y-auto" style={{ maxHeight: 160 }}>
        {AGENTS.map((agent) => {
          const isActive = activeAgents.has(agent.id)
          const isIdle = status === "idle"
          return (
            <div
              key={agent.id}
              className={`flex items-center gap-2 rounded px-2 py-1.5 transition-colors ${
                isActive ? "bg-indigo-900/30 border border-indigo-500/20" : "bg-slate-800/20"
              }`}
            >
              <span className={`h-2 w-2 rounded-full shrink-0 ${agent.color} ${isActive ? "animate-pulse" : "opacity-25"}`} />
              <span className={`text-[13px] font-medium truncate flex-1 ${isActive ? "text-slate-100" : "text-slate-500"}`}>
                {agent.label}
              </span>
              <span className={`text-[11px] font-semibold shrink-0 ${
                isActive ? "text-emerald-400" : isIdle ? "text-slate-600" : "text-slate-700"
              }`}>
                {isActive ? "活跃" : isIdle ? "就绪" : "待机"}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
