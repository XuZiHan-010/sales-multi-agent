# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Sales Multi-Agent** — A multi-agent production-sales coordination system for FMCG beverages using Contract Net Protocol.

The system detects market demand shocks (livestream events, competitor promos, weather, supply disruptions) and automatically orchestrates 7 intelligent agents (1 Coordinator, 3 Sales, 10 Inventory, 3 Production) to negotiate and allocate inventory in <2 hours, targeting >90% demand fulfillment while minimizing procurement cost and stockout losses.

**Tech Stack:**
- **Frontend:** Next.js 14 + React 18 + Tailwind CSS + Zustand (state)
- **Backend:** FastAPI + LangGraph (orchestration) + Prophet (time-series forecasting)
- **Communication:** FIPA-ACL messages (agents), SSE (real-time events to frontend)

## Quick Start

### Frontend
```bash
cd frontend
npm install
npm run dev          # dev server at localhost:3000
npm run build        # production build (checks TS, lints)
npm run lint         # eslint check
```

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# Test: curl http://localhost:8000/health
```

Both must run simultaneously for the demo to work. Frontend calls `/api/*` endpoints on the backend.

## Codebase Structure

### Backend Architecture (`backend/`)

**6-node LangGraph state machine** (`graph/negotiation_graph.py`):
1. `node_sense_signal` — Parse market signals (livestream, competitor, weather, supply_shock) into demand shocks + factory faults
2. `node_federated_forecast` — 3 Sales agents run local Prophet forecasts + Laplace noise (ε=0.03 for privacy), broadcast global demand view
3. `node_sense_demand` — Detect shortage gaps (72h demand vs. current inventory); trigger shortage events
4. `node_apply_faults` — Mark equipment faults (reduce factory SKU capacity by 30%)
5. `node_broadcast_cfp` — Coordinator issues Call-For-Proposals per shortage; Inventory/Production agents bid
6. `node_finalize` — Aggregate results (total awarded qty, unmet qty, cost, stockout loss avoided)

Output: Full audit trail in `event_log` (streamed to frontend via SSE) + `negotiation_results` (bid traces, Coordinator decisions).

**Key Agents** (`agents/`):
- `coordinator_agent.py` — Runs Contract Net Protocol (CFP → PROPOSE → ACCEPT/REJECT → INFORM). Scores proposals by: cost × time weight + risk multiplier. Greedy best-cost selection until demand met or no more valid bids.
- `inventory_agent.py` × 10 — Query mock inventory, propose available qty + transport cost/time.
- `production_agent.py` × 3 — Query mock factory capacity (reduced by faults), propose producible qty + lead time cost.
- `market_signal_agent.py` — Inject market signals (hardcoded in routes or custom via API).

**Data** (`data/generate_mock_data.py`):
- 3 regions (华北, 华东, 华南) × 6 SKUs × 3 factories × 10 warehouses
- Sales history (180 days, with seasonality/weekly patterns)
- Inventory snapshots
- Factory capacity matrix + transport cost/time matrix

**API** (`api/routes.py`):
- `POST /api/run` — Trigger scenario. Body: `{scenario_id, market_signals?, demand_shocks?, factory_faults?}`. Returns `{run_id, status: "pending"}`.
- `GET /api/events/{run_id}` — SSE stream. Emits raw event objects from `state.event_log`. Closes on `stream_end`.
- `GET /api/result/{run_id}` — Fetch final result after run completes. Includes `negotiation_results`, `federated_forecasts`.
- `GET /api/meta`, `/api/inventory`, `/api/factory`, `/api/sales/history` — Static data endpoints.

**Important:** All NumPy types from Prophet/LightGBM are converted to Python natives via `_convert_to_serializable()` before JSON response (prevents serialization errors).

### Frontend Architecture (`frontend/`)

**Page Layout** (`src/app/page.tsx`):
- Left (col-span-3): Agent status panel + event timeline (flex-1 scrollable)
- Center (col-span-6): Negotiation graph (nodes, SVG lines, live commentary)
- Right (col-span-3): Scenario panel (tab: preset/custom) + results panel (flex-1 scrollable)

**State Management** (`src/store/scenarioStore.ts` + Zustand):
- Central store for `runId`, `status`, `events[]`, `negotiationResults[]`, `federatedForecasts`, `finalSummary`
- Methods: `pushEvent`, `setResults`, `setForecasts`, `setStatus`, `reset`

**Real-time Flow** (`src/hooks/useScenario.ts`):
1. User triggers scenario (preset or custom)
2. `triggerScenario(scenarioId, customPayload?)` calls `POST /api/run`
3. Receives `run_id`, immediately starts `EventSource("/api/events/{run_id}")`
4. Each SSE message parsed as JSON and pushed to store via `pushEvent`
5. On `stream_end`, closes EventSource and calls `GET /api/result/{run_id}` to fetch results

**Key Components:**
- `NegotiationGraph.tsx` — Central visual orchestration. Renders:
  - 7 agent nodes (absolutely positioned, glow when active)
  - SVG lines between nodes with flowing dots (animated via `animateMotion` + `mpath`)
  - **LiveCommentary** floating card (center, z-index 4): Shows latest event with icon + colored card, auto-switches per SSE pulse. On done, shows 🏁 + final metrics.
- `ScenarioPanel.tsx` — Two-tab form:
  - Preset tab: 3 hardcoded scenarios (main, competitor, weather)
  - Custom tab: Form fields (signal_type, sku, region, multiplier, duration, factory) → constructs `{market_signals: [...]}` payload
- `EventTimeline.tsx` — Scrolling list of events (icon, timestamp, message, reasoning)
- `ResultsPanel.tsx` — Metrics cards, fill-rate donut chart, bid comparison bar chart, federated forecast summary, Coordinator decision rationale
- `AgentStatusPanel.tsx` — 7-agent status grid with activity pulse + state label (active/ready/idle)

**Styling:** Tailwind CSS + custom animations in `globals.css` (fade-in, slide-in, slide-up, edge-pulse). Dark theme: `#080c1a` bg, indigo/cyan accent.

## Event Flow Example (Main Scenario)

1. User selects "Main scenario" (livestream SKU-A ×3 + factory fault -30%)
2. Backend `node_sense_signal` converts into demand_shocks + factory_faults
3. `node_federated_forecast` runs 3 local Prophet models in parallel + noise
4. `node_sense_demand` detects shortage (72h demand > current stock)
5. `node_broadcast_cfp` issues CFP to all Inventory + Production agents
6. Agents propose: Inventory sends transport-based offers, Production sends lead-time-based offers
7. Coordinator scores each by: `cost_per_unit * (1 + risk_factor)` + time penalty
8. Greedy selection until shortage met or no more valid bids
9. Each decision logged as `accept_sent` or implicit rejection
10. Final aggregation in `node_finalize`: total awarded, unmet, cost, loss avoided
11. Frontend displays result: "已协调 12000 箱 / 成本 ¥500K / 避免损失 ¥2500万"

## Common Development Tasks

### Add a new market signal type
1. Define case in `backend/agents/market_signal_agent.py:MOCK_EVENTS` (dict with signal_type, sku, region, demand_multiplier, duration_hours, description)
2. Update `backend/graph/negotiation_graph.py:node_sense_signal()` to handle the new signal_type branch
3. Update frontend `src/components/ScenarioPanel.tsx:SIGNAL_TYPES` array for form option
4. Add icon/color to `src/components/NegotiationGraph.tsx:LIVE_CFG` for real-time card display

### Modify agent bid scoring logic
- Edit `backend/agents/coordinator_agent.py:_score_proposal()` method
- Current: `score = (cost_per_unit + time_penalty) * risk_multiplier`
- Rebuild frontend (`npm run build`) to ensure no breakage in Coordinator summary display

### Adjust node positions or graph sizing
- Edit `src/components/NegotiationGraph.tsx:NODES` array (x, y as % of container)
- Change `containerRef` height constraints in same file
- Vertical compression: reduce y% gaps to fit within viewport without scroll

### Extend result metrics
1. Add new fields to `backend/agents/coordinator_agent.py:NegotiationResult` (Pydantic model)
2. Add aggregation logic in `backend/graph/negotiation_graph.py:node_finalize()`
3. Add display card in `frontend/src/components/ResultsPanel.tsx:MetricCard` or new chart

## Key Files & Patterns

| File | Purpose |
|---|---|
| `backend/graph/negotiation_graph.py` | LangGraph state machine; core orchestration logic |
| `backend/agents/coordinator_agent.py` | Contract Net Protocol implementation; bid scoring & decision |
| `backend/api/routes.py` | FastAPI endpoints; NumPy serialization; SSE event stream |
| `frontend/src/store/scenarioStore.ts` | Zustand store; single source of truth for UI state |
| `frontend/src/hooks/useScenario.ts` | SSE subscription + result fetch logic |
| `frontend/src/components/NegotiationGraph.tsx` | Graph visualization + LiveCommentary card (main visual feedback) |
| `frontend/src/components/ScenarioPanel.tsx` | Preset + custom signal input UI |

**Critical pattern — SSE + Zustand:**
- Backend emits raw event objects: `{id, type, timestamp, message, [optional fields]}`
- Frontend `useScenario` parses each line and calls `store.pushEvent(ev)`
- Store update triggers React re-render; `NegotiationGraph` reads `latestEvent` and animates card
- No polling, no delta computation; pure event-driven architecture

## Debugging Tips

- **Graph not animating?** Check `status === "running"` in `NegotiationGraph`. Verify `activeAgents` Set is populated from `events`. SVG `animateMotion` requires predefined `<path>` in `<defs>` with `id`, plus `<mpath href="#id">`.
- **Nodes not showing?** Ensure `nodeRefs` populated on mount. Check `SvgLines` 80ms delay for `getBoundingClientRect()`. If nodes invisible, check `z-index` stacking (SVG at z-index 1, nodes div at z-index 2, overlays at z-index 3+).
- **Events not streaming?** Verify backend SSE `/events/{run_id}` endpoint. Check browser Network tab for 200 + text/event-stream Content-Type. Ensure `_runs[run_id]` exists in backend state.
- **TypeScript errors?** `npm run build` in frontend folder. Common: missing `?` on optional fields (e.g., `ev.message?`), wrong Zustand action signatures, or NumPy type leaking into frontend JSON.

## Environment Variables

**Frontend** (`.env.local`):
- `NEXT_PUBLIC_API_BASE` — Backend API root (default: `http://localhost:8000/api`)

**Backend** (`.env` or shell):
- `OPENAI_API_KEY` — Required for LangChain/LLM features (Coordinator reasoning, Market Signal LLM analysis)
- `EXA_API_KEY` (optional) — For real-time web search in MarketSignalAgent.search_and_signal()

## Testing & Build

- **Frontend lint:** `npm run lint` (eslint + next/recommended rules)
- **Frontend build:** `npm run build` (next build; checks TS, generates .next/)
- **Backend test:** No formal test suite yet. Manual SSE test: `curl -N http://localhost:8000/api/events/{run_id}` after triggering a run
- **Cache issues:** If webpack errors occur, delete `.next` folder and rebuild

## Deployment Notes

- **Vercel (Frontend):** Supports Next.js out-of-the-box. Set `NEXT_PUBLIC_API_BASE` env var pointing to backend domain.
- **Railway / Render (Backend):** FastAPI ASGI-compatible. Include `requirements.txt`. Mock data generated at startup via `ensure_mock_data()`.
- **Database:** Currently in-memory (demo only). For production, replace `_runs` dict with persistent store (PostgreSQL, MongoDB).
