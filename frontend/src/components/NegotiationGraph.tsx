"use client"
import { useScenarioStore, type ScenarioEvent } from "@/store/scenarioStore"
import { useMemo, useRef, useEffect, useState } from "react"
import { agentsForEvent, edgeForEvent, bubbleLabel } from "@/lib/agentEventMap"

interface NegResult {
  trace?: Array<{ status: string; type: string }>
}

// ── Live commentary event config (icon + color per event type) ────────────────
const LIVE_CFG: Record<string, { icon: string; tint: string; accent: string; label: string }> = {
  signal_received:    { icon: "📡", tint: "rgba(124,58,237,0.2)", accent: "#a78bfa", label: "外部信号" },
  fed_forecast_start: { icon: "🔬", tint: "rgba(14,116,144,0.2)", accent: "#67e8f9", label: "联邦预测" },
  forecast_risk:      { icon: "⚠️", tint: "rgba(202,138,4,0.2)",  accent: "#fde047", label: "风险预警" },
  sense_demand:       { icon: "🔍", tint: "rgba(37,99,235,0.2)",  accent: "#93c5fd", label: "需求感知" },
  shortage_detected:  { icon: "🚨", tint: "rgba(220,38,38,0.2)",  accent: "#fca5a5", label: "缺货检测" },
  factory_fault:      { icon: "🔧", tint: "rgba(234,88,12,0.2)",  accent: "#fdba74", label: "供给冲击" },
  cfp_issued:         { icon: "📢", tint: "rgba(79,70,229,0.22)", accent: "#a5b4fc", label: "发起招标" },
  propose_received:   { icon: "💬", tint: "rgba(16,185,129,0.2)", accent: "#6ee7b7", label: "收到投标" },
  accept_sent:        { icon: "✅", tint: "rgba(21,128,61,0.22)", accent: "#86efac", label: "中标确认" },
  no_shortage:        { icon: "✅", tint: "rgba(21,128,61,0.22)", accent: "#86efac", label: "无需协同" },
  risk_assessed:      { icon: "🛡️", tint: "rgba(217,119,6,0.18)",  accent: "#fbbf24", label: "风险评估" },
  finalized:          { icon: "🏁", tint: "rgba(79,70,229,0.22)", accent: "#c7d2fe", label: "协同完成" },
}

// ── Node positions (% of container w/h) ──────────────────────────────────────
const NODES = [
  { id: "market_signal", label: "Market Signal", role: "外部信号",  color: "#7c3aed", glow: "rgba(124,58,237,0.55)", x: 50, y: 8  },
  { id: "coordinator",   label: "Coordinator",   role: "调度仲裁",  color: "#4338ca", glow: "rgba(67,56,202,0.55)",  x: 50, y: 26 },
  { id: "sales_north",   label: "Sales 华北",    role: "需求预测",  color: "#0e7490", glow: "rgba(14,116,144,0.55)", x: 15, y: 47 },
  { id: "sales_east",    label: "Sales 华东",    role: "需求预测",  color: "#0e7490", glow: "rgba(14,116,144,0.55)", x: 50, y: 47 },
  { id: "sales_south",   label: "Sales 华南",    role: "需求预测",  color: "#0e7490", glow: "rgba(14,116,144,0.55)", x: 85, y: 47 },
  { id: "inv",           label: "Inventory ×10", role: "库存调拨",  color: "#b45309", glow: "rgba(180,83,9,0.55)",   x: 28, y: 70 },
  { id: "prod",          label: "Production ×3", role: "排产投标",  color: "#9f1239", glow: "rgba(159,18,57,0.55)",  x: 72, y: 70 },
  { id: "risk",          label: "Risk Agent",    role: "风险监控",  color: "#d97706", glow: "rgba(217,119,6,0.6)",   x: 84, y: 8  },
]

const EDGES = [
  { id: "ms-co",   from: "market_signal", to: "coordinator" },
  { id: "co-sn",   from: "coordinator",   to: "sales_north" },
  { id: "co-se",   from: "coordinator",   to: "sales_east"  },
  { id: "co-ss",   from: "coordinator",   to: "sales_south" },
  { id: "co-inv",  from: "coordinator",   to: "inv"         },
  { id: "co-prd",  from: "coordinator",   to: "prod"        },
  { id: "inv-prd", from: "inv",           to: "prod"        },
  { id: "co-risk", from: "coordinator",   to: "risk"        },
]

// ── Bubble & Flow types ──────────────────────────────────────────────────────
interface Bubble {
  id: string
  nodeId: string
  label: string
  color: string
  expiresAt: number
}

interface FlowToken {
  id: string
  edgeId: string
  reverse: boolean
  label: string
  color: string
  expiresAt: number
}

// ── Data hook ─────────────────────────────────────────────────────────────────
function useGraphData() {
  const { events, negotiationResults, status, finalSummary } = useScenarioStore()

  const activeAgents = useMemo(() => {
    const s = new Set<string>()
    events.forEach((ev) => agentsForEvent(ev).forEach((id) => s.add(id)))
    return s
  }, [events])

  const acceptedAgents = useMemo(() => {
    const s = new Set<string>()
    ;(negotiationResults as NegResult[]).forEach((r) =>
      r.trace?.filter(t => t.status === "ACCEPTED").forEach(t =>
        s.add(t.type === "inventory" ? "inv" : "prod")
      )
    )
    return s
  }, [negotiationResults])

  const latestEvent = useMemo<ScenarioEvent | null>(() => {
    return events.length ? events[events.length - 1] : null
  }, [events])

  return { events, activeAgents, acceptedAgents, latestEvent, eventCount: events.length, status, finalSummary }
}

// ── Hook: maintain transient bubbles + flow tokens from event stream ─────────
function useEventAnimations(events: ScenarioEvent[]) {
  const [bubbles, setBubbles] = useState<Bubble[]>([])
  const [flows, setFlows] = useState<FlowToken[]>([])
  const processedIds = useRef<Set<string>>(new Set())

  useEffect(() => {
    const now = Date.now()
    const newBubbles: Bubble[] = []
    const newFlows: FlowToken[] = []

    for (const ev of events) {
      if (processedIds.current.has(ev.id)) continue
      processedIds.current.add(ev.id)

      // Node bubbles: attach to first mapped agent
      const targets = agentsForEvent(ev)
      if (targets.length > 0) {
        const cfg = LIVE_CFG[ev.type]
        const color = cfg?.accent ?? "#94a3b8"
        // Primary bubble: pick the "source" agent (first target is usually the acting one)
        newBubbles.push({
          id: `${ev.id}-bubble`,
          nodeId: targets[0],
          label: bubbleLabel(ev),
          color,
          expiresAt: now + 3500,
        })
      }

      // Edge flow tokens
      const edge = edgeForEvent(ev)
      if (edge) {
        newFlows.push({
          id: `${ev.id}-flow`,
          edgeId: edge.edgeId,
          reverse: edge.reverse,
          label: edge.label,
          color: edge.color,
          expiresAt: now + 2500,
        })
      }
    }

    if (newBubbles.length) setBubbles((cur) => [...cur, ...newBubbles])
    if (newFlows.length) setFlows((cur) => [...cur, ...newFlows])
  }, [events])

  // Cleanup expired items every 500ms
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now()
      setBubbles((cur) => cur.filter((b) => b.expiresAt > now))
      setFlows((cur) => cur.filter((f) => f.expiresAt > now))
    }, 500)
    return () => clearInterval(interval)
  }, [])

  // Reset when events array clears (new run)
  useEffect(() => {
    if (events.length === 0) {
      processedIds.current = new Set()
      setBubbles([])
      setFlows([])
    }
  }, [events.length])

  return { bubbles, flows }
}

// ── Line data type ────────────────────────────────────────────────────────────
interface LineData {
  id: string; x1: number; y1: number; x2: number; y2: number; color: string; active: boolean
}

// ── SVG overlay: lines + flowing dots + event text tokens ─────────────────────
function SvgLines({
  containerRef, nodeRefs, activeAgents, isRunning, flows,
}: {
  containerRef: React.RefObject<HTMLDivElement | null>
  nodeRefs: React.MutableRefObject<Record<string, HTMLDivElement | null>>
  activeAgents: Set<string>
  isRunning: boolean
  flows: FlowToken[]
}) {
  const [lines, setLines] = useState<LineData[]>([])

  useEffect(() => {
    const calculate = () => {
      const container = containerRef.current
      if (!container) return
      const cRect = container.getBoundingClientRect()
      if (cRect.width === 0) return  // not laid out yet
      const next: LineData[] = []
      for (const edge of EDGES) {
        const fromEl = nodeRefs.current[edge.from]
        const toEl   = nodeRefs.current[edge.to]
        if (!fromEl || !toEl) continue
        const fR = fromEl.getBoundingClientRect()
        const tR = toEl.getBoundingClientRect()
        if (fR.width === 0 || tR.width === 0) continue
        const x1 = fR.left + fR.width / 2 - cRect.left
        const y1 = fR.top  + fR.height    - cRect.top
        const x2 = tR.left + tR.width / 2 - cRect.left
        const y2 = tR.top                 - cRect.top
        const src = NODES.find(n => n.id === edge.from)!
        const active = activeAgents.has(edge.from) && activeAgents.has(edge.to)
        next.push({ id: edge.id, x1, y1, x2, y2, color: src.color, active })
      }
      if (next.length > 0) setLines(next)
    }

    // 1. Try immediately
    calculate()

    // 2. ResizeObserver: fires when container gets real dimensions
    let observer: ResizeObserver | null = null
    if (containerRef.current) {
      observer = new ResizeObserver(() => { calculate(); observer?.disconnect(); observer = null })
      observer.observe(containerRef.current)
    }

    // 3. Fallback for slow renders
    const timer = setTimeout(calculate, 300)

    window.addEventListener("resize", calculate)
    return () => {
      clearTimeout(timer)
      observer?.disconnect()
      window.removeEventListener("resize", calculate)
    }
  }, [containerRef, nodeRefs, activeAgents, isRunning])

  const lineById = useMemo(() => {
    const m = new Map<string, LineData>()
    lines.forEach((l) => m.set(l.id, l))
    return m
  }, [lines])

  return (
    <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 1 }}>
      <defs>
        <filter id="ln-glow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="4" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        {lines.map(l => (
          <path key={`def-${l.id}`}
            id={`edge-path-${l.id}`}
            d={`M ${l.x1} ${l.y1} L ${l.x2} ${l.y2}`}
            fill="none" stroke="none"
          />
        ))}
      </defs>

      {lines.map(l => (
        <g key={l.id}>
          <line x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2}
            stroke={l.active ? l.color : "#334155"}
            strokeWidth={l.active ? 2 : 1}
            strokeOpacity={l.active ? 0.6 : 0.18}
          />
          {l.active && (
            <line x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2}
              stroke={l.color} strokeWidth={7} strokeOpacity={0.13}
              filter="url(#ln-glow)"
            />
          )}
          {l.active && isRunning && (
            <circle r="4.5" fill={l.color} opacity="0.95" filter="url(#ln-glow)">
              <animateMotion repeatCount="indefinite" dur="1.6s">
                <mpath href={`#edge-path-${l.id}`} />
              </animateMotion>
            </circle>
          )}
        </g>
      ))}

      {/* Flowing event tokens: labeled badge traveling along the edge */}
      {flows.map((f) => {
        const line = lineById.get(f.edgeId)
        if (!line) return null
        const kp = f.reverse ? "1;0" : "0;1"
        return (
          <g key={f.id}>
            {/* Use animateMotion on a group containing circle + text */}
            <g>
              <rect x={-40} y={-10} width={80} height={20} rx={10}
                fill="rgba(8,12,26,0.92)" stroke={f.color} strokeWidth={1.2} />
              <text
                x={0} y={4} textAnchor="middle"
                fontSize={10} fontWeight={600} fill={f.color}
              >
                {f.label}
              </text>
              <animateMotion
                dur="2.2s"
                repeatCount="1"
                fill="remove"
                calcMode="linear"
                keyPoints={kp}
                keyTimes="0;1"
              >
                <mpath href={`#edge-path-${f.edgeId}`} />
              </animateMotion>
            </g>
          </g>
        )
      })}
    </svg>
  )
}

// ── Node bubble: transient callout next to a node ─────────────────────────────
function NodeBubble({ label, color }: { label: string; color: string }) {
  return (
    <div
      className="animate-slide-up"
      style={{
        position: "absolute",
        left: "calc(100% + 10px)",
        top: "50%",
        transform: "translateY(-50%)",
        minWidth: 130,
        maxWidth: 220,
        padding: "6px 10px",
        borderRadius: 8,
        border: `1px solid ${color}66`,
        background: "rgba(8,12,26,0.95)",
        boxShadow: `0 0 12px ${color}33`,
        fontSize: 11,
        fontWeight: 500,
        color: "#e2e8f0",
        lineHeight: 1.3,
        whiteSpace: "nowrap",
        overflow: "hidden",
        textOverflow: "ellipsis",
        zIndex: 5,
        pointerEvents: "none",
      }}
    >
      <span style={{ color }}>{label}</span>
    </div>
  )
}

// ── Status strip (running) ────────────────────────────────────────────────────
function StatusStrip({
  latestEvent, eventCount, status,
}: {
  latestEvent: ScenarioEvent | null
  eventCount: number
  status: string
}) {
  const isRunning = status === "running"
  const ev = latestEvent
  const cfg = ev
    ? (LIVE_CFG[ev.type] ?? { icon: "·", tint: "rgba(71,85,105,0.15)", accent: "#94a3b8", label: ev.type })
    : null

  if (status === "idle") {
    return (
      <div className="shrink-0 border-t border-slate-700/40 px-4 py-2.5 text-[13px] text-slate-600 text-center"
        style={{ background: "rgba(6,9,20,0.95)" }}>
        触发场景后节点逐步激活、连线实时流动
      </div>
    )
  }

  if (!isRunning || !ev || !cfg) return null

  return (
    <div className="shrink-0 border-t border-slate-700/40" style={{ background: "rgba(6,9,20,0.95)" }}>
      <div
        key={ev.id ?? `${ev.type}-${eventCount}`}
        className="animate-slide-up px-4 py-2.5 flex items-center gap-3"
      >
        <span className="text-xl shrink-0">{cfg.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[12px] font-semibold uppercase tracking-wider" style={{ color: cfg.accent }}>
              {cfg.label}
            </span>
            <span className="text-[11px] text-slate-600">#{eventCount}</span>
          </div>
          <p className="text-[13px] text-slate-200 truncate">{ev.message ?? ev.type}</p>
        </div>
      </div>
    </div>
  )
}

// ── Completion banner: sits between header and canvas (shrink-0, never squishes graph) ──
function CompletionBanner({
  finalSummary, eventCount,
}: {
  finalSummary: ScenarioEvent | null
  eventCount: number
}) {
  if (!finalSummary) return null
  const awarded  = finalSummary.total_awarded
  const cost     = finalSummary.total_cost
  const unmet    = finalSummary.total_unmet
  const fillRate = (awarded !== undefined && unmet !== undefined && (awarded + unmet) > 0)
    ? Math.round(awarded / (awarded + unmet) * 100)
    : null

  return (
    <div
      className="shrink-0 animate-fade-in border-b border-indigo-500/25 px-4 py-2 flex items-center gap-4"
      style={{ background: "linear-gradient(135deg, rgba(15,18,40,0.98) 0%, rgba(30,27,75,0.95) 100%)" }}
    >
      <span className="text-sm">🏁</span>
      <span className="text-[12px] font-bold text-indigo-200">协同完成</span>
      <span className="text-[11px] text-slate-500">共 {eventCount} 步</span>
      <div className="flex items-center gap-4 ml-2">
        <span className="text-[13px] font-bold text-emerald-300">{fillRate !== null ? `${fillRate}%` : "—"} <span className="text-[10px] text-slate-500 font-normal">满足率</span></span>
        <span className="text-[13px] font-bold text-cyan-300">{awarded !== undefined ? `${awarded.toLocaleString()}箱` : "—"} <span className="text-[10px] text-slate-500 font-normal">协调量</span></span>
        <span className="text-[13px] font-bold text-indigo-300">{cost !== undefined ? `¥${(cost / 1000).toFixed(0)}K` : "—"} <span className="text-[10px] text-slate-500 font-normal">成本</span></span>
      </div>
      <button
        onClick={() => {
          const el = document.querySelector("[data-panel='results']")
          el?.scrollIntoView({ behavior: "smooth", block: "start" })
        }}
        className="ml-auto shrink-0 flex items-center gap-1 rounded-lg px-2.5 py-1 text-[11px] font-semibold text-indigo-300 border border-indigo-500/40 bg-indigo-900/30 hover:bg-indigo-800/40 transition-colors whitespace-nowrap"
      >
        查看摘要 ↓
      </button>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function NegotiationGraph() {
  const { events, activeAgents, acceptedAgents, latestEvent, eventCount, status, finalSummary } = useGraphData()
  const { bubbles, flows } = useEventAnimations(events)
  const isRunning = status === "running"
  const isDone    = status === "done"

  const containerRef = useRef<HTMLDivElement>(null)
  const nodeRefs     = useRef<Record<string, HTMLDivElement | null>>({})

  // Build per-node latest bubble (only show one bubble per node, most recent)
  const bubblesByNode = useMemo(() => {
    const m = new Map<string, Bubble>()
    bubbles.forEach((b) => m.set(b.nodeId, b))
    return m
  }, [bubbles])

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: "#080c1a" }}>

      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-700/40 flex items-center justify-between shrink-0">
        <h2 className="text-base font-semibold text-slate-200 tracking-wide">谈判轨迹</h2>
        <div className="flex items-center gap-3 text-[12px]">
          {isRunning && (
            <span className="text-emerald-400 flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"/>谈判进行中
            </span>
          )}
          {isDone && (
            <span className="text-cyan-400 flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400"/>协同完成
            </span>
          )}
          {status === "idle" && (
            <span className="text-slate-500">选择场景并触发后节点激活</span>
          )}
        </div>
      </div>

      {/* Completion banner — flow element above canvas, never squishes nodes */}
      {isDone && <CompletionBanner finalSummary={finalSummary} eventCount={eventCount} />}

      {/* Node + SVG canvas */}
      <div ref={containerRef} className="relative flex-1 min-h-0 overflow-hidden" style={{ minHeight: 320 }}>
        {/* Grid */}
        <div className="absolute inset-0 pointer-events-none" style={{
          backgroundImage: "linear-gradient(rgba(79,70,229,0.06) 1px,transparent 1px),linear-gradient(90deg,rgba(79,70,229,0.06) 1px,transparent 1px)",
          backgroundSize: "44px 44px",
        }}/>
        <SvgLines
          containerRef={containerRef}
          nodeRefs={nodeRefs}
          activeAgents={activeAgents}
          isRunning={isRunning}
          flows={flows}
        />

        {/* Node divs on top */}
        <div className="absolute inset-0" style={{ zIndex: 2 }}>
          {NODES.map(node => {
            const active   = activeAgents.has(node.id)
            const accepted = acceptedAgents.has(node.id)
            const scale    = active ? "translate(-50%, -50%) scale(1.08)" : "translate(-50%, -50%) scale(1)"
            const bubble   = bubblesByNode.get(node.id)
            return (
              <div
                key={node.id}
                ref={el => { nodeRefs.current[node.id] = el }}
                style={{
                  position: "absolute",
                  left: `${node.x}%`,
                  top:  `${node.y}%`,
                  transform: scale,
                  minWidth: 110,
                  border: `2px solid ${active ? node.color : "#2d3748"}`,
                  boxShadow: active ? `0 0 20px ${node.glow}, inset 0 0 10px ${node.glow}` : "none",
                  background: active ? `${node.color}1c` : "rgba(8,12,26,0.9)",
                  borderRadius: 12,
                  padding: "10px 16px",
                  textAlign: "center",
                  transition: "all 0.4s ease",
                }}
              >
                {active && (
                  <span style={{ position:"absolute", top:-6, right:-6, display:"flex", width:12, height:12 }}>
                    <span className="animate-ping" style={{
                      position:"absolute", inset:0, borderRadius:"50%",
                      background: node.color, opacity: 0.65,
                    }}/>
                    <span style={{ width:12, height:12, borderRadius:"50%", background: node.color }}/>
                  </span>
                )}
                {accepted && (
                  <span className="animate-pulse" style={{
                    position:"absolute", inset:-4, borderRadius:14,
                    border:"2px solid rgba(74,222,128,0.75)", pointerEvents:"none",
                  }}/>
                )}
                <div style={{ fontSize:14, fontWeight:700, color: active ? "#f8fafc" : "#94a3b8", lineHeight:1.3 }}>
                  {node.label}
                </div>
                <div style={{ fontSize:12, marginTop:3, color: active ? node.color : "#475569" }}>
                  {node.role}
                </div>

                {/* Transient event bubble next to the node */}
                {bubble && (
                  <NodeBubble key={bubble.id} label={bubble.label} color={bubble.color} />
                )}
              </div>
            )
          })}
        </div>

      </div>

      <StatusStrip
        latestEvent={latestEvent}
        eventCount={eventCount}
        status={status}
      />

    </div>
  )
}
