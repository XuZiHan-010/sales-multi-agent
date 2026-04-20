"use client"
import { useScenarioStore, type RiskItem } from "@/store/scenarioStore"
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend
} from "recharts"

// ── KPI card ──────────────────────────────────────────────────────────────────
function KpiCard({ label, value, sub, highlight }: {
  label: string; value: string; sub?: string; highlight?: boolean
}) {
  return (
    <div className={`rounded-xl p-3 text-center border ${
      highlight ? "bg-indigo-900/40 border-indigo-500/30" : "bg-slate-800/50 border-slate-700/30"
    }`}>
      <p className={`text-xl font-bold ${highlight ? "text-indigo-200" : "text-slate-200"}`}>{value}</p>
      <p className="text-[12px] text-slate-400 mt-0.5">{label}</p>
      {sub && <p className="text-[10px] text-slate-600 mt-0.5">{sub}</p>}
    </div>
  )
}

// ── Risk warning banner ───────────────────────────────────────────────────────
function RiskBanner({ riskEntries }: { riskEntries: { sku: string; regions: string[] }[] }) {
  if (riskEntries.length === 0) return null
  return (
    <div className="rounded-xl border border-amber-500/40 bg-amber-900/20 p-4">
      <div className="flex items-center gap-2 mb-2.5">
        <span className="text-base">⚠️</span>
        <h3 className="text-sm font-bold text-amber-300">缺货风险预警</h3>
      </div>
      <div className="flex flex-col gap-2">
        {riskEntries.map(({ sku, regions }) => (
          <div key={sku} className="flex items-center gap-2 flex-wrap">
            <span className="text-[12px] font-semibold text-slate-200 shrink-0">{sku}</span>
            {regions.map((r) => (
              <span key={r} className="text-[11px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                {r}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Risk Agent assessment panel ───────────────────────────────────────────────
const RISK_ICONS: Record<string, string> = { shortage: "📦", overload: "⚡", lead_time: "⏱️" }
const RISK_NAMES: Record<string, string> = { shortage: "缺货风险", overload: "产能超载", lead_time: "交期延误" }

function RiskAssessmentPanel({ risks }: { risks: RiskItem[] }) {
  const hasHigh = risks.some(r => r.level === "high")
  return (
    <div className={`rounded-xl border p-4 ${
      risks.length === 0
        ? "border-emerald-500/25 bg-emerald-900/10"
        : hasHigh
          ? "border-red-500/35 bg-red-900/10"
          : "border-amber-500/30 bg-amber-900/10"
    }`}>
      <div className="flex items-center gap-2 mb-2.5">
        <span className="text-base">🛡️</span>
        <h3 className="text-sm font-bold text-amber-300">Risk Agent 评估</h3>
        <span className={`ml-auto text-[10px] px-2 py-0.5 rounded-full font-semibold border ${
          risks.length === 0
            ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
            : hasHigh
              ? "bg-red-500/20 text-red-300 border-red-500/30"
              : "bg-amber-500/20 text-amber-300 border-amber-500/30"
        }`}>
          {risks.length === 0 ? "✓ 无风险" : hasHigh ? "⚠ 高风险" : "△ 中风险"}
        </span>
      </div>

      {risks.length === 0 ? (
        <p className="text-[12px] text-slate-400">当前协同方案无缺货、超载或交期风险。</p>
      ) : (
        <div className="flex flex-col gap-1.5">
          {risks.map((risk, i) => (
            <div key={i} className={`flex items-start gap-2.5 rounded-lg px-3 py-2 ${
              risk.level === "high"
                ? "bg-red-900/25 border border-red-500/20"
                : "bg-amber-900/20 border border-amber-500/20"
            }`}>
              <span className="text-sm shrink-0 mt-0.5">{RISK_ICONS[risk.type] ?? "⚠️"}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[11px] font-semibold text-slate-300">{RISK_NAMES[risk.type] ?? risk.type}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
                    risk.level === "high" ? "bg-red-500/30 text-red-300" : "bg-amber-500/30 text-amber-300"
                  }`}>{risk.level === "high" ? "高" : "中"}</span>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">{risk.message}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Coordinator summary card ──────────────────────────────────────────────────
function CoordinatorSummary({ results }: { results: { sku: string; region: string; summary: string }[] }) {
  const withSummary = results.filter(r => r.summary)
  if (withSummary.length === 0) return null
  return (
    <div className="rounded-xl border border-indigo-500/30 bg-indigo-900/20 p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-base">🧠</span>
        <h3 className="text-sm font-bold text-indigo-200">Coordinator 决策摘要</h3>
      </div>
      <div className="flex flex-col gap-3">
        {withSummary.map((r) => (
          <div key={r.sku + r.region}>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[12px] font-bold text-indigo-300">{r.sku}</span>
              <span className="text-[11px] px-1.5 py-0.5 rounded bg-slate-700/50 text-slate-400">{r.region}</span>
            </div>
            <p className="text-[12px] text-slate-300 leading-relaxed">{r.summary}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Federated forecast ────────────────────────────────────────────────────────
function ForecastSummary({ forecasts }: {
  forecasts: Record<string, { total_demand_72h: number; peak_region: string; shortage_risk: Record<string, boolean> }>
}) {
  const entries = Object.entries(forecasts)
  if (entries.length === 0) return null
  return (
    <div className="rounded-xl border border-cyan-500/20 bg-[#1a1d2e]/80 p-4">
      <h3 className="text-sm font-semibold text-slate-200 mb-2">联邦预测摘要</h3>
      <div className="flex flex-col gap-2">
        {entries.map(([sku, view]) => {
          const riskRegions = Object.entries(view.shortage_risk).filter(([, v]) => v).map(([r]) => r)
          return (
            <div key={sku} className="rounded-lg bg-slate-800/50 px-3 py-2">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-semibold text-slate-100">{sku}</span>
                <span className="text-[11px] text-slate-400">峰值：{view.peak_region}</span>
              </div>
              <p className="text-[12px] text-slate-300 mt-1">
                72h 总需求 <span className="font-semibold text-cyan-300">
                  {view.total_demand_72h.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </span> 箱
              </p>
              {riskRegions.length > 0 && (
                <p className="text-[11px] text-yellow-400 mt-1">⚠️ {riskRegions.join("、")}</p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Bid bar chart ─────────────────────────────────────────────────────────────
function BidChart({ traces }: { traces: { agent: string; qty: number; cost: number; status: string }[] }) {
  const data = traces.map(t => ({
    name: t.agent.replace("inventory_", "inv_").replace("production_", "prod_").slice(0, 14),
    qty: t.qty,
    fill: t.status === "ACCEPTED" ? "#6366f1" : "#374151",
  }))
  return (
    <ResponsiveContainer width="100%" height={110}>
      <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <XAxis dataKey="name" tick={{ fontSize: 8, fill: "#64748b" }} interval={0} angle={-30} textAnchor="end" height={36} />
        <YAxis tick={{ fontSize: 8, fill: "#64748b" }} />
        <Tooltip
          contentStyle={{ background: "#1e293b", border: "1px solid #334155", fontSize: 12 }}
          labelStyle={{ color: "#94a3b8" }}
          formatter={(v) => [`${Number(v).toLocaleString()} 箱`, "数量"]}
        />
        <Bar dataKey="qty" radius={[3, 3, 0, 0]}>
          {data.map((d, i) => <Cell key={i} fill={d.fill} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

// ── Fill rate donut ───────────────────────────────────────────────────────────
function FillRateDonut({ awarded, unmet }: { awarded: number; unmet: number }) {
  const total = awarded + unmet
  if (total === 0) return null
  const data = [
    { name: "已协同", value: awarded, fill: "#6366f1" },
    { name: "未满足", value: unmet,   fill: "#ef4444" },
  ]
  return (
    <ResponsiveContainer width="100%" height={90}>
      <PieChart>
        <Pie data={data} cx="50%" cy="50%" innerRadius={26} outerRadius={38} dataKey="value" paddingAngle={2}>
          {data.map((d, i) => <Cell key={i} fill={d.fill} />)}
        </Pie>
        <Legend iconSize={8} wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
        <Tooltip
          contentStyle={{ background: "#1e293b", border: "1px solid #334155", fontSize: 12 }}
          formatter={(v) => [`${Number(v).toLocaleString()} 箱`]}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function ResultsPanel() {
  const { negotiationResults, status, federatedForecasts, riskAssessment } = useScenarioStore()

  const totalAwarded  = negotiationResults.reduce((s, r) => s + (r.awarded_qty ?? 0), 0)
  const totalRequired = negotiationResults.reduce((s, r) => s + (r.required_qty ?? 0), 0)
  const totalUnmet    = negotiationResults.reduce((s, r) => s + (r.unmet_qty ?? 0), 0)
  const totalCost     = negotiationResults.reduce((s, r) => s + (r.total_cost ?? 0), 0)
  const totalLoss     = negotiationResults.reduce((s, r) => s + (r.stockout_loss ?? 0), 0)
  const fillRate      = totalRequired > 0 ? (totalAwarded / totalRequired * 100) : 0
  const allTraces     = negotiationResults.flatMap(r => r.trace)
  const isDone        = status === "done"

  const riskEntries = Object.entries(federatedForecasts)
    .map(([sku, view]) => ({
      sku,
      regions: Object.entries(view.shortage_risk).filter(([, v]) => v).map(([r]) => r),
    }))
    .filter(e => e.regions.length > 0)

  return (
    <div className="flex flex-col gap-3 p-1">

      {/* 1 — KPI 指标（始终显示） */}
      <div className="rounded-xl border border-indigo-500/20 bg-[#1a1d2e]/80 p-4">
        <h2 className="text-sm font-bold text-slate-200 mb-3">协同效果</h2>
        <div className="grid grid-cols-2 gap-2">
          <KpiCard label="需求满足率" value={isDone ? `${fillRate.toFixed(1)}%` : "—"} sub="目标 >90%" highlight />
          <KpiCard label="响应时间"   value="< 2h" sub="传统 3–5天" highlight />
          <KpiCard label="协同成本"   value={totalCost > 0 ? `¥${(totalCost / 1000).toFixed(0)}K` : "—"} />
          <KpiCard label="避免损失"   value={totalLoss > 0 ? `¥${(totalLoss / 10000).toFixed(1)}万` : "—"} />
        </div>
      </div>

      {/* 2 — 风险预警（最显眼位置） */}
      {isDone && <RiskBanner riskEntries={riskEntries} />}

      {/* 2b — Risk Agent 评估结果 */}
      {isDone && riskAssessment !== null && <RiskAssessmentPanel risks={riskAssessment} />}

      {/* 3 — Coordinator 决策摘要（AI 核心价值） */}
      {isDone && (
        <CoordinatorSummary
          results={negotiationResults.map(r => ({ sku: r.sku, region: r.region, summary: r.summary }))}
        />
      )}

      {/* 4 — 联邦预测摘要 */}
      {isDone && <ForecastSummary forecasts={federatedForecasts} />}

      {/* 5 — 需求满足分布 */}
      {isDone && totalRequired > 0 && (
        <div className="rounded-xl border border-indigo-500/20 bg-[#1a1d2e]/80 p-4">
          <h3 className="text-sm font-semibold text-slate-200 mb-2">需求满足分布</h3>
          <FillRateDonut awarded={totalAwarded} unmet={totalUnmet} />
        </div>
      )}

      {/* 6 — 投标对比 */}
      {allTraces.length > 0 && (
        <div className="rounded-xl border border-indigo-500/20 bg-[#1a1d2e]/80 p-4">
          <h3 className="text-sm font-semibold text-slate-200 mb-2">投标对比（蓝=中标）</h3>
          <BidChart traces={allTraces} />
        </div>
      )}

    </div>
  )
}
