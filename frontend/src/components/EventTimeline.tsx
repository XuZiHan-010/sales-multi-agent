"use client"
import { useScenarioStore, type ScenarioEvent } from "@/store/scenarioStore"
import { useEffect, useRef } from "react"

const EVENT_CFG: Record<string, { icon: string; color: string; label: string }> = {
  signal_received:    { icon: "📡", color: "text-purple-400",  label: "外部信号" },
  fed_forecast_start: { icon: "🔬", color: "text-cyan-400",    label: "联邦预测" },
  forecast_risk:      { icon: "⚠️", color: "text-yellow-400",  label: "风险预警" },
  sense_demand:       { icon: "🔍", color: "text-blue-400",    label: "需求感知" },
  shortage_detected:  { icon: "🚨", color: "text-red-400",     label: "缺货检测" },
  factory_fault:      { icon: "🔧", color: "text-orange-400",  label: "供给冲击" },
  cfp_issued:         { icon: "📢", color: "text-indigo-400",  label: "发起招标" },
  propose_received:   { icon: "💬", color: "text-emerald-400", label: "收到投标" },
  accept_sent:        { icon: "✅", color: "text-green-400",   label: "中标确认" },
  no_shortage:        { icon: "✅", color: "text-green-400",   label: "无需协同" },
  finalized:          { icon: "🏁", color: "text-indigo-300",  label: "协同完成" },
}

function EventRow({ ev }: { ev: ScenarioEvent }) {
  const cfg = EVENT_CFG[ev.type] ?? { icon: "·", color: "text-slate-400", label: ev.type }
  const ts = ev.timestamp?.slice(11, 19) ?? ""
  return (
    <div className="flex gap-2 py-2 border-b border-slate-800/60 animate-fade-in">
      <span className="text-lg shrink-0 mt-0.5">{cfg.icon}</span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 mb-1">
          <span className={`text-[12px] font-semibold ${cfg.color}`}>{cfg.label}</span>
          <span className="text-[11px] text-slate-600 ml-auto shrink-0">{ts}</span>
        </div>
        <p className="text-[13px] text-slate-300 leading-snug">{ev.message}</p>
        {ev.reasoning && (
          <p className="text-[12px] text-slate-500 mt-1 italic line-clamp-2">└ {ev.reasoning}</p>
        )}
      </div>
    </div>
  )
}

export default function EventTimeline() {
  const { events, status } = useScenarioStore()
  const bottomRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60
    if (isAtBottom) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }
  }, [events.length])

  return (
    <div className="rounded-xl border border-indigo-500/20 bg-[#1a1d2e]/80 flex flex-col overflow-hidden">
      <div className="px-3 py-3 border-b border-slate-700/50 flex items-center justify-between shrink-0">
        <h2 className="text-base font-semibold text-slate-200">事件流</h2>
        <div>
          {status === "running" && (
            <span className="flex items-center gap-1 text-[12px] text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />运行中
            </span>
          )}
          {status === "done" && (
            <span className="text-[12px] text-indigo-400">{events.length} 条事件</span>
          )}
          {status === "idle" && (
            <span className="text-[12px] text-slate-600">待触发</span>
          )}
        </div>
      </div>

      {/* Fixed-height scrolling window: show 8 events max */}
      <div ref={scrollRef} className="h-80 overflow-y-auto px-3 py-1 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
        {events.length === 0 && status === "idle" && (
          <div className="flex items-center justify-center h-full">
            <p className="text-[12px] text-slate-600 text-center leading-relaxed">
              触发场景后<br />实时事件显示在此
            </p>
          </div>
        )}
        {events.map((ev) => (
          <EventRow key={ev.id ?? ev.timestamp} ev={ev} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
