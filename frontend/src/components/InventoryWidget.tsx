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

// Show these SKUs × regions as summary bars (top 3 most interesting)
const WATCH_LIST = [
  { sku: "SKU-A", region: "华南" },
  { sku: "SKU-A", region: "华东" },
  { sku: "SKU-B", region: "华东" },
]

function aggregate(rows: InventoryRow[]): Record<string, Record<string, number>> {
  const out: Record<string, Record<string, number>> = {}
  for (const r of rows) {
    if (!out[r.sku]) out[r.sku] = {}
    out[r.sku][r.region] = (out[r.sku][r.region] ?? 0) + r.current_stock
  }
  return out
}

function StockBar({ sku, region, current, max }: { sku: string; region: string; current: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (current / max) * 100) : 0
  const low = pct < 25
  const mid = pct < 50
  const barColor = low ? "#ef4444" : mid ? "#f59e0b" : "#34d399"

  return (
    <div className="flex items-center gap-2.5">
      <div className="text-[12px] text-slate-400 w-20 shrink-0">
        <span className="font-semibold text-slate-300">{sku}</span>
        <span className="text-slate-500"> {region}</span>
      </div>
      <div className="flex-1 h-2 rounded-full bg-slate-800 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: barColor }}
        />
      </div>
      <span className={`text-[11px] font-mono shrink-0 ${low ? "text-red-400" : mid ? "text-amber-400" : "text-emerald-400"}`}>
        {current.toLocaleString()}
      </span>
    </div>
  )
}

export default function InventoryWidget({ refreshKey }: { refreshKey?: number }) {
  const [rows, setRows] = useState<InventoryRow[]>([])
  const [baseline, setBaseline] = useState<Record<string, Record<string, number>>>({})
  const [resetting, setResetting] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const fetchInventory = useCallback(async () => {
    try {
      const res = await fetch(`${API}/inventory/live`)
      if (!res.ok) return
      const data: InventoryRow[] = await res.json()
      setRows(data)
      setBaseline((prev) => {
        if (Object.keys(prev).length === 0) return aggregate(data)
        return prev
      })
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { fetchInventory() }, [fetchInventory, refreshKey])

  const handleReset = async () => {
    setResetting(true)
    try {
      await fetch(`${API}/inventory/reset`, { method: "POST" })
      setBaseline({})
      await fetchInventory()
    } finally {
      setResetting(false)
    }
  }

  const current = aggregate(rows)

  const watchItems = WATCH_LIST.map(({ sku, region }) => ({
    sku,
    region,
    current: current[sku]?.[region] ?? 0,
    max: baseline[sku]?.[region] ?? 1,
  }))

  const allSkus = Array.from(new Set(rows.map(r => r.sku))).sort()

  return (
    <div className="rounded-xl border border-slate-700/40 bg-[#1a1d2e]/80 overflow-hidden">
      <div className="px-3 py-2.5 flex items-center justify-between">
        <button
          onClick={() => setExpanded((e) => !e)}
          className="flex items-center gap-1.5 text-left flex-1"
        >
          <span className="text-[13px] font-semibold text-slate-300">库存水位</span>
          <span className="text-[11px] text-slate-600 ml-1">{expanded ? "▲" : "▼"}</span>
        </button>
        <button
          onClick={handleReset}
          disabled={resetting}
          className="text-[11px] text-slate-500 hover:text-slate-300 transition-colors px-2 py-0.5 rounded hover:bg-slate-700/40 disabled:opacity-40"
        >
          {resetting ? "重置中…" : "重置"}
        </button>
      </div>

      <div className="px-3 pb-3 flex flex-col gap-2">
        {watchItems.map(({ sku, region, current: cur, max }) => (
          <StockBar key={`${sku}-${region}`} sku={sku} region={region} current={cur} max={max} />
        ))}
      </div>

      {expanded && (
        <div className="px-3 pb-3 border-t border-slate-700/30 pt-3 flex flex-col gap-2">
          {allSkus.map(sku =>
            Object.keys(current[sku] ?? {}).map(region => (
              <StockBar
                key={`${sku}-${region}`}
                sku={sku}
                region={region}
                current={current[sku]?.[region] ?? 0}
                max={baseline[sku]?.[region] ?? 1}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}
