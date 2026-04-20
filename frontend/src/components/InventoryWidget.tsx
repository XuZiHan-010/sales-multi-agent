"use client"
import { useEffect, useState, useCallback } from "react"

const API = process.env.NEXT_PUBLIC_API_BASE ?? "/api"

interface InventoryRow {
  warehouse: string
  region: string
  sku: string
  current_stock: number
  safety_stock: number
  in_transit: number
}

function aggregate(rows: InventoryRow[]): { sku: string; region: string; current: number; max: number }[] {
  const map: Record<string, { current: number; max: number }> = {}
  for (const r of rows) {
    const key = `${r.sku}||${r.region}`
    if (!map[key]) map[key] = { current: 0, max: 0 }
    map[key].current += r.current_stock
    map[key].max += r.current_stock + r.safety_stock
  }
  return Object.entries(map)
    .map(([key, v]) => {
      const [sku, region] = key.split("||")
      return { sku, region, ...v }
    })
    .sort((a, b) => {
      // Sort by stock level ascending (lowest first — most urgent)
      const pctA = a.max > 0 ? a.current / a.max : 0
      const pctB = b.max > 0 ? b.current / b.max : 0
      return pctA - pctB
    })
}

function StockBar({ sku, region, current, max }: { sku: string; region: string; current: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (current / max) * 100) : 0
  const low = pct < 25
  const mid = pct < 50
  const barColor = low ? "#ef4444" : mid ? "#f59e0b" : "#34d399"

  return (
    <div className="flex items-center gap-2.5 py-1">
      <div className="text-[12px] w-20 shrink-0">
        <span className="font-semibold text-slate-300">{sku}</span>
        <span className="text-slate-500"> {region}</span>
      </div>
      <div className="flex-1 h-2 rounded-full bg-slate-800 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: barColor }}
        />
      </div>
      <span className={`text-[11px] font-mono shrink-0 w-14 text-right ${low ? "text-red-400" : mid ? "text-amber-400" : "text-emerald-400"}`}>
        {current.toLocaleString()}
      </span>
    </div>
  )
}

export default function InventoryWidget({ refreshKey }: { refreshKey?: number }) {
  const [items, setItems] = useState<{ sku: string; region: string; current: number; max: number }[]>([])
  const [baseline, setBaseline] = useState<{ sku: string; region: string; current: number; max: number }[]>([])
  const [resetting, setResetting] = useState(false)

  const fetchInventory = useCallback(async () => {
    try {
      const res = await fetch(`${API}/inventory/live`)
      if (!res.ok) return
      const data: InventoryRow[] = await res.json()
      const agg = aggregate(data)
      setItems(agg)
      setBaseline((prev) => prev.length === 0 ? agg : prev)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { fetchInventory() }, [fetchInventory, refreshKey])

  const handleReset = async () => {
    setResetting(true)
    try {
      await fetch(`${API}/inventory/reset`, { method: "POST" })
      setBaseline([])
      await fetchInventory()
    } finally {
      setResetting(false)
    }
  }

  // Merge current values against baseline maxes
  const display = items.map((item) => {
    const base = baseline.find(b => b.sku === item.sku && b.region === item.region)
    return { ...item, max: base?.current ?? item.max }
  })

  const lowCount = display.filter(d => d.max > 0 && d.current / d.max < 0.25).length

  return (
    <div className="rounded-xl border border-slate-700/40 bg-[#1a1d2e]/80 flex flex-col min-h-0">
      {/* Header */}
      <div className="px-3 py-2.5 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-semibold text-slate-300">库存水位</span>
          {display.length > 0 && (
            <span className="text-[10px] text-slate-600">{display.length} 项</span>
          )}
          {lowCount > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-500/15 text-red-400 border border-red-500/25">
              {lowCount} 低库存
            </span>
          )}
        </div>
        <button
          onClick={handleReset}
          disabled={resetting}
          className="text-[11px] text-slate-500 hover:text-slate-300 transition-colors px-2 py-0.5 rounded hover:bg-slate-700/40 disabled:opacity-40"
        >
          {resetting ? "重置中…" : "重置"}
        </button>
      </div>

      {/* Scrollable list — shows ~5 rows, scroll for more */}
      <div className="px-3 pb-2.5 overflow-y-auto flex flex-col divide-y divide-slate-700/20" style={{ maxHeight: 160 }}>
        {display.length === 0 ? (
          <p className="text-[11px] text-slate-600 py-2">加载中…</p>
        ) : (
          display.map(({ sku, region, current, max }) => (
            <StockBar key={`${sku}-${region}`} sku={sku} region={region} current={current} max={max} />
          ))
        )}
      </div>
    </div>
  )
}
