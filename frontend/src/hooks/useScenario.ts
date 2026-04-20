"use client"
import { useCallback, useRef } from "react"
import { useScenarioStore, type ScenarioEvent } from "@/store/scenarioStore"

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api"

export function useScenario() {
  // Use individual selectors so useCallback deps are stable function references
  const reset       = useScenarioStore((s) => s.reset)
  const startRun    = useScenarioStore((s) => s.startRun)
  const pushEvent   = useScenarioStore((s) => s.pushEvent)
  const setStatus   = useScenarioStore((s) => s.setStatus)
  const setResults  = useScenarioStore((s) => s.setResults)
  const setForecasts = useScenarioStore((s) => s.setForecasts)

  // Store active EventSource so we can close it on component unmount or new run
  const evtSourceRef = useRef<EventSource | null>(null)
  const drainTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const triggerScenario = useCallback(async (
    scenarioId: string,
    customPayload?: {
      market_signals?: unknown[]
      demand_shocks?: Record<string, unknown>
      factory_faults?: Record<string, unknown>
    },
  ) => {
    // Close any existing stream before starting a new run
    evtSourceRef.current?.close()
    evtSourceRef.current = null
    if (drainTimerRef.current) {
      clearTimeout(drainTimerRef.current)
      drainTimerRef.current = null
    }

    reset()

    const body = customPayload
      ? { scenario_id: scenarioId, ...customPayload }
      : { scenario_id: scenarioId }

    const res = await fetch(`${API_BASE}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error("Failed to start run")
    const { run_id } = await res.json()
    startRun(run_id)

    const evtSource = new EventSource(`${API_BASE}/events/${run_id}`)
    evtSourceRef.current = evtSource

    // Queue-based replay: animate events 350ms apart even on batched delivery
    const eventQueue: ScenarioEvent[] = []
    let isProcessing = false
    let pendingEnd: { status: string } | null = null

    const drainQueue = () => {
      if (eventQueue.length === 0) {
        isProcessing = false
        if (pendingEnd) {
          const finalStatus = pendingEnd.status === "error" ? "error" : "done"
          setStatus(finalStatus)
          if (finalStatus === "done") {
            fetch(`${API_BASE}/result/${run_id}`)
              .then((r) => {
                if (!r.ok) throw new Error(`Result fetch failed: ${r.status}`)
                return r.json()
              })
              .then((data) => {
                if (data.negotiation_results) setResults(data.negotiation_results)
                if (data.federated_forecasts) setForecasts(data.federated_forecasts)
              })
              .catch((err) => console.error("[useScenario] fetchResult error:", err))
          }
          pendingEnd = null
        }
        return
      }
      isProcessing = true
      pushEvent(eventQueue.shift()!)
      drainTimerRef.current = setTimeout(drainQueue, 350)
    }

    evtSource.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data) as ScenarioEvent & { status?: string }
        if (ev.type === "stream_end") {
          evtSource.close()
          evtSourceRef.current = null
          pendingEnd = { status: ev.status ?? "" }
          if (!isProcessing) drainQueue()
          return
        }
        eventQueue.push(ev)
        if (!isProcessing) drainQueue()
      } catch (err) {
        console.warn("[useScenario] SSE parse error:", err, e.data)
      }
    }

    evtSource.onerror = () => {
      evtSource.close()
      evtSourceRef.current = null
      setStatus("error")
    }
  }, [reset, startRun, pushEvent, setStatus, setResults, setForecasts])

  return { triggerScenario }
}
