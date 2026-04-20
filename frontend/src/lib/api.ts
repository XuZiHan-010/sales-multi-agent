const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api"

export async function fetchMeta() {
  const res = await fetch(`${API_BASE}/meta`)
  if (!res.ok) throw new Error("Failed to fetch meta")
  return res.json()
}

export async function fetchInventory() {
  const res = await fetch(`${API_BASE}/inventory`)
  if (!res.ok) throw new Error("Failed to fetch inventory")
  return res.json()
}

export async function fetchFactory() {
  const res = await fetch(`${API_BASE}/factory`)
  if (!res.ok) throw new Error("Failed to fetch factory")
  return res.json()
}

export async function fetchSalesHistory(region?: string, sku?: string) {
  const params = new URLSearchParams()
  if (region) params.set("region", region)
  if (sku) params.set("sku", sku)
  const res = await fetch(`${API_BASE}/sales/history?${params}`)
  if (!res.ok) throw new Error("Failed to fetch sales history")
  return res.json()
}
