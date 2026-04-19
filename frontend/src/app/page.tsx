"use client"
import { useEffect, useState } from "react"
import AgentStatusPanel from "@/components/AgentStatusPanel"
import EventTimeline from "@/components/EventTimeline"
import NegotiationGraph from "@/components/NegotiationGraph"
import ScenarioPanel from "@/components/ScenarioPanel"
import ResultsPanel from "@/components/ResultsPanel"
import InventoryWidget from "@/components/InventoryWidget"
import { useScenarioStore } from "@/store/scenarioStore"

type MobileTab = "trigger" | "graph" | "results"

function MobileTabBar({
  activeTab,
  onChange,
  status,
  hasResults,
}: {
  activeTab: MobileTab
  onChange: (t: MobileTab) => void
  status: string
  hasResults: boolean
}) {
  const tabs: { id: MobileTab; icon: string; label: string; pulse?: boolean; badge?: boolean }[] = [
    { id: "trigger", icon: "⚡", label: "触发信号" },
    { id: "graph",   icon: "🔗", label: "谈判轨迹", pulse: status === "running" },
    { id: "results", icon: "📊", label: "协同效果", badge: hasResults },
  ]
  return (
    <nav
      className="shrink-0 flex items-stretch border-t border-slate-700/60"
      style={{ background: "#0a0c18", height: 56 }}
    >
      {tabs.map(({ id, icon, label, pulse, badge }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className={`flex-1 flex flex-col items-center justify-center gap-0.5 relative transition-colors
            ${activeTab === id ? "text-indigo-400" : "text-slate-500 hover:text-slate-300"}`}
        >
          {(pulse || badge) && (
            <span className={`absolute top-2 right-[calc(50%-18px)] h-2 w-2 rounded-full
              ${pulse ? "bg-emerald-400 animate-pulse" : "bg-cyan-400"}`}
            />
          )}
          <span className="text-xl leading-none">{icon}</span>
          <span className="text-[11px] font-medium mt-0.5">{label}</span>
          {activeTab === id && (
            <span className="absolute bottom-0 inset-x-4 h-0.5 rounded-full bg-indigo-400" />
          )}
        </button>
      ))}
    </nav>
  )
}

export default function Home() {
  const { status } = useScenarioStore()
  const [invRefreshKey, setInvRefreshKey] = useState(0)
  const [activeTab, setActiveTab] = useState<MobileTab>("trigger")

  // Auto-switch tabs on mobile
  useEffect(() => {
    if (status === "running") setActiveTab("graph")
    if (status === "done") {
      setInvRefreshKey((k) => k + 1)
      const t = setTimeout(() => setActiveTab("results"), 1800)
      return () => clearTimeout(t)
    }
  }, [status])

  const hasResults = status === "done"

  return (
    <main className="h-screen bg-[#0f1117] text-slate-200 flex flex-col overflow-hidden">

      {/* ── Header ── */}
      <header className="border-b border-indigo-500/20 px-4 sm:px-6 py-2.5 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2 sm:gap-3">
          <div className="h-7 w-7 rounded-lg bg-indigo-600/80 flex items-center justify-center text-sm shrink-0">🤝</div>
          <div className="min-w-0">
            <h1 className="text-base font-bold text-indigo-300 leading-tight">Sales Multi-Agent</h1>
            <p className="text-[11px] text-slate-500 hidden sm:block">多智能体产销协同 · 快消饮料</p>
          </div>
        </div>
        {/* Desktop meta */}
        <div className="hidden lg:flex items-center gap-4 text-[12px] text-slate-500">
          <span>3 大区 · 10 仓库 · 3 工厂</span>
          <span className="flex items-center gap-1 text-emerald-500">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />就绪
          </span>
        </div>
        {/* Mobile status pill */}
        <div className="lg:hidden text-[12px]">
          {status === "running" && (
            <span className="flex items-center gap-1.5 text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />运行中
            </span>
          )}
          {status === "done" && (
            <span className="flex items-center gap-1.5 text-cyan-400">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />完成
            </span>
          )}
          {status === "idle" && (
            <span className="text-slate-600">就绪</span>
          )}
        </div>
      </header>

      {/* ══════════════════════════════════════════════
          DESKTOP (lg+): 3-column fixed-height grid
      ══════════════════════════════════════════════ */}
      <div
        className="hidden lg:grid lg:grid-cols-12 gap-2 p-2 flex-1 overflow-hidden"
        style={{ minHeight: 0 }}
      >
        {/* Left: Agent + Inventory + EventTimeline */}
        <aside className="lg:col-span-3 flex flex-col gap-2 min-h-0 overflow-hidden">
          {/* AgentStatusPanel: capped so EventTimeline always gets space */}
          <div className="shrink-0 overflow-hidden" style={{ maxHeight: 260 }}>
            <AgentStatusPanel />
          </div>
          <div className="shrink-0">
            <InventoryWidget refreshKey={invRefreshKey} />
          </div>
          <div className="flex-1 min-h-0 overflow-hidden">
            <EventTimeline />
          </div>
        </aside>

        {/* Center: Negotiation graph */}
        <section className="lg:col-span-6 rounded-xl border border-cyan-500/20 bg-[#0d0f1e] overflow-hidden flex flex-col min-h-0">
          <NegotiationGraph />
        </section>

        {/* Right: ScenarioPanel + ResultsPanel — whole column scrolls so dropdowns aren't clipped */}
        <aside className="lg:col-span-3 min-h-0 overflow-y-auto flex flex-col gap-2 pb-2">
          <ScenarioPanel />
          <div data-panel="results">
            <ResultsPanel />
          </div>
        </aside>
      </div>

      {/* ══════════════════════════════════════════════
          TABLET (md–lg): 2-column layout
      ══════════════════════════════════════════════ */}
      <div
        className="hidden md:flex lg:hidden gap-2 p-2 flex-1 overflow-hidden"
        style={{ minHeight: 0 }}
      >
        {/* Left: Graph (60%) */}
        <section className="rounded-xl border border-cyan-500/20 bg-[#0d0f1e] overflow-hidden flex flex-col min-h-0" style={{ flex: 3 }}>
          <NegotiationGraph />
        </section>

        {/* Right: Controls + Results (40%) — whole column scrolls */}
        <aside className="min-h-0 overflow-y-auto flex flex-col gap-2 pb-2" style={{ flex: 2 }}>
          <ScenarioPanel />
          <InventoryWidget refreshKey={invRefreshKey} />
          <div data-panel="results">
            <ResultsPanel />
          </div>
        </aside>
      </div>

      {/* ══════════════════════════════════════════════
          MOBILE (<md): Tab-based single-panel
      ══════════════════════════════════════════════ */}
      <div className="flex md:hidden flex-1 flex-col overflow-hidden" style={{ minHeight: 0 }}>

        {/* Panel area */}
        <div className="flex-1 min-h-0 overflow-hidden">

          {/* Trigger tab */}
          {activeTab === "trigger" && (
            <div className="h-full overflow-y-auto">
              <div className="p-3">
                <ScenarioPanel />
              </div>
            </div>
          )}

          {/* Graph tab */}
          {activeTab === "graph" && (
            <div className="h-full flex flex-col bg-[#0d0f1e] overflow-hidden">
              <NegotiationGraph />
            </div>
          )}

          {/* Results tab */}
          {activeTab === "results" && (
            <div
              data-panel="results"
              className="h-full overflow-y-auto"
            >
              <div className="p-3 flex flex-col gap-3">
                <AgentStatusPanel />
                <InventoryWidget refreshKey={invRefreshKey} />
                <ResultsPanel />
                <EventTimeline />
              </div>
            </div>
          )}

        </div>

        {/* Bottom tab bar */}
        <MobileTabBar
          activeTab={activeTab}
          onChange={setActiveTab}
          status={status}
          hasResults={hasResults}
        />
      </div>

    </main>
  )
}
