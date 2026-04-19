"use client"
import { useScenario } from "@/hooks/useScenario"
import { useScenarioStore } from "@/store/scenarioStore"
import { useState } from "react"

// Signal types matching backend schema
const SIGNAL_TYPES = [
  { value: "livestream",   label: "直播带货",  hint: "KOL/主播直播导致 SKU 需求激增" },
  { value: "competitor",   label: "竞品冲击",  hint: "竞品断货/涨价，本品承接溢出" },
  { value: "weather",      label: "气候异常",  hint: "高温/寒潮/台风等气候冲击" },
  { value: "supply_shock", label: "供给冲击",  hint: "工厂故障/原料短缺导致产能下降" },
  { value: "news",         label: "新闻舆情",  hint: "政策/热点事件引发需求波动" },
]

const SKUS      = ["SKU-A", "SKU-B", "SKU-C", "SKU-D", "SKU-E", "SKU-F"]
const REGIONS   = ["华北", "华东", "华南"]
const FACTORIES = ["天津厂", "上海厂", "广州厂"]
const DURATIONS = [24, 48, 72, 96]

// Quick-fill templates — these replace the old preset buttons
const TEMPLATES = [
  {
    label: "直播爆单",
    icon: "📺",
    fill: { signalType: "livestream", sku: "SKU-A", region: "华南", multiplier: 3.0, duration: 48, factory: "广州厂",
      description: "头部主播直播带货 SKU-A，预计带动华南区需求激增 3 倍" },
  },
  {
    label: "竞品断货",
    icon: "⚔️",
    fill: { signalType: "competitor", sku: "SKU-B", region: "华东", multiplier: 2.0, duration: 72, factory: "上海厂",
      description: "竞品促销活动，华东 SKU-B 预计承接溢出需求（×2.0）" },
  },
  {
    label: "高温冲击",
    icon: "🌡️",
    fill: { signalType: "weather", sku: "SKU-A", region: "华南", multiplier: 1.5, duration: 96, factory: "广州厂",
      description: "华南地区高温预警（>38°C），功能饮料需求上涨 50%" },
  },
  {
    label: "产线故障",
    icon: "🔧",
    fill: { signalType: "supply_shock", sku: "SKU-A", region: "华南", multiplier: 1.0, duration: 24, factory: "广州厂",
      description: "广州厂 SKU-A 产线设备故障，产能下降 30%" },
  },
]

function autoDesc(signalType: string, sku: string, region: string, multiplier: number) {
  const r = region || "全国"
  const s = sku || "多 SKU"
  switch (signalType) {
    case "livestream":   return `头部主播直播带货 ${s}，预计带动${r}需求激增 ${multiplier.toFixed(1)} 倍`
    case "competitor":   return `竞品促销活动，${r} ${s} 预计承接溢出需求（×${multiplier.toFixed(1)}）`
    case "weather":      return `${r}异常气候，${s} 需求上涨 ${Math.round((multiplier - 1) * 100)}%`
    case "supply_shock": return `生产端供给冲击，${s} 产能下降`
    case "news":         return `${r} ${s} 受新闻热点影响，需求波动 ×${multiplier.toFixed(1)}`
    default: return ""
  }
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-[12px] text-slate-400 mb-1.5 font-semibold uppercase tracking-wider">{label}</label>
      {children}
    </div>
  )
}

export default function ScenarioPanel() {
  const { triggerScenario } = useScenario()
  const { status } = useScenarioStore()
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const [signalType, setSignalType]   = useState("livestream")
  const [sku, setSku]                 = useState("SKU-A")
  const [region, setRegion]           = useState("华南")
  const [multiplier, setMultiplier]   = useState(3.0)
  const [duration, setDuration]       = useState(48)
  const [factory, setFactory]         = useState("广州厂")
  const [description, setDescription] = useState(autoDesc("livestream", "SKU-A", "华南", 3.0))
  const [descTouched, setDescTouched] = useState(false)

  const isRunning = status === "running" || loading

  const applyTemplate = (t: typeof TEMPLATES[0]) => {
    const f = t.fill
    setSignalType(f.signalType)
    setSku(f.sku)
    setRegion(f.region)
    setMultiplier(f.multiplier)
    setDuration(f.duration)
    setFactory(f.factory)
    setDescription(f.description)
    setDescTouched(false)
  }

  const updateField = (fn: () => void, regen: { signalType?: string; sku?: string; region?: string; multiplier?: number }) => {
    fn()
    if (!descTouched) {
      setDescription(autoDesc(
        regen.signalType ?? signalType,
        regen.sku ?? sku,
        regen.region ?? region,
        regen.multiplier ?? multiplier,
      ))
    }
  }

  const handleTrigger = async () => {
    setError(null)
    setLoading(true)
    const signal: Record<string, unknown> = {
      signal_type: signalType,
      region: region || null,
      sku: sku || null,
      demand_multiplier: signalType === "supply_shock" ? 1.0 : multiplier,
      duration_hours: duration,
      description: description.trim() || autoDesc(signalType, sku, region, multiplier),
      source: "operator_input",
    }
    if (signalType === "supply_shock" && sku) {
      signal.factory_fault = { factory, skus: [sku] }
    }
    try {
      await triggerScenario("custom", { market_signals: [signal] })
    } catch (e) {
      setError((e as Error)?.message ?? "启动失败，请检查后端是否运行")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-xl border border-indigo-500/20 bg-[#1a1d2e]/80 p-3">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-base font-bold text-slate-200">触发市场信号</h2>
        <span className="text-[11px] text-slate-500 bg-slate-800/60 px-2.5 py-0.5 rounded-full">生产模式</span>
      </div>

      {/* Quick-fill template chips */}
      <div className="mb-3">
        <p className="text-[11px] text-slate-500 mb-2 uppercase tracking-wider font-semibold">快速填充</p>
        <div className="grid grid-cols-2 gap-1">
          {TEMPLATES.map((t) => (
            <button
              key={t.label}
              onClick={() => applyTemplate(t)}
              disabled={isRunning}
              className={`flex items-center gap-1.5 text-left rounded-lg px-3 py-2 border text-[13px] font-medium transition-all
                border-slate-700/50 bg-slate-800/40 text-slate-300
                hover:border-indigo-500/40 hover:bg-indigo-900/20 hover:text-slate-100
                ${isRunning ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
            >
              <span>{t.icon}</span>
              <span>{t.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="h-px bg-slate-700/40 mb-3" />

      {/* Form */}
      <div className="flex flex-col gap-2.5">
        <Field label="信号类型">
          <select
            value={signalType}
            onChange={(e) => updateField(() => setSignalType(e.target.value), { signalType: e.target.value })}
            disabled={isRunning}
            className="form-select"
          >
            {SIGNAL_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
          <p className="text-[11px] text-slate-500 mt-1">
            {SIGNAL_TYPES.find(t => t.value === signalType)?.hint}
          </p>
        </Field>

        <div className="grid grid-cols-2 gap-2">
          <Field label="目标 SKU">
            <select
              value={sku}
              onChange={(e) => updateField(() => setSku(e.target.value), { sku: e.target.value })}
              disabled={isRunning}
              className="form-select"
            >
              <option value="">不限</option>
              {SKUS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="目标区域">
            <select
              value={region}
              onChange={(e) => updateField(() => setRegion(e.target.value), { region: e.target.value })}
              disabled={isRunning}
              className="form-select"
            >
              <option value="">全国</option>
              {REGIONS.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </Field>
        </div>

        {signalType !== "supply_shock" && (
          <Field label={`需求倍数  ×${multiplier.toFixed(1)}`}>
            <input
              type="range" min={1} max={5} step={0.1}
              value={multiplier}
              onChange={(e) => updateField(() => setMultiplier(Number(e.target.value)), { multiplier: Number(e.target.value) })}
              disabled={isRunning}
              className="w-full accent-indigo-500"
            />
            <div className="flex justify-between text-[10px] text-slate-600 mt-1">
              <span>×1.0 平稳</span><span>×3.0 激增</span><span>×5.0 爆单</span>
            </div>
          </Field>
        )}

        {signalType === "supply_shock" && (
          <Field label="故障工厂">
            <select
              value={factory}
              onChange={(e) => setFactory(e.target.value)}
              disabled={isRunning}
              className="form-select"
            >
              {FACTORIES.map(f => <option key={f} value={f}>{f}</option>)}
            </select>
          </Field>
        )}

        <div className="grid grid-cols-2 gap-2">
          <Field label="持续时长">
            <select
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              disabled={isRunning}
              className="form-select"
            >
              {DURATIONS.map(d => <option key={d} value={d}>{d}h</option>)}
            </select>
          </Field>
          <Field label="信号来源">
            <input
              type="text"
              value="operator_input"
              readOnly
              className="form-select opacity-50 cursor-default"
            />
          </Field>
        </div>

        <Field label="事件描述">
          <textarea
            value={description}
            onChange={(e) => { setDescription(e.target.value); setDescTouched(true) }}
            disabled={isRunning}
            rows={2}
            className="w-full rounded-md bg-slate-900/70 border border-slate-700/60 text-[11px] text-slate-200 px-2 py-1.5 focus:outline-none focus:border-indigo-500/60 resize-none"
          />
        </Field>

        <button
          onClick={handleTrigger}
          disabled={isRunning}
          className={`w-full rounded-lg px-4 py-3 text-base font-bold transition-all mt-1
            ${isRunning
              ? "bg-slate-700 text-slate-500 cursor-not-allowed"
              : "bg-indigo-600 hover:bg-indigo-500 text-white active:scale-95 shadow-lg shadow-indigo-900/40"
            }`}
        >
          {isRunning ? (
            <span className="flex items-center justify-center gap-2">
              <span className="h-3 w-3 rounded-full border-2 border-slate-400 border-t-transparent animate-spin" />
              协同进行中…
            </span>
          ) : "▶ 触发协同"}
        </button>
      </div>

      {error && (
        <p className="mt-3 text-[12px] text-red-400 text-center">{error}</p>
      )}


      <style jsx>{`
        .form-select {
          width: 100%;
          border-radius: 6px;
          background: rgba(15, 23, 42, 0.7);
          border: 1px solid rgba(51, 65, 85, 0.6);
          color: #e2e8f0;
          font-size: 13px;
          padding: 7px 10px;
          outline: none;
        }
        .form-select:focus { border-color: rgba(99, 102, 241, 0.6); }
        .form-select:disabled { opacity: 0.5; cursor: not-allowed; }
      `}</style>
    </div>
  )
}
