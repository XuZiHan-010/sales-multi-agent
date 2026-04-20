# Sales Multi-Agent Coordination System
## 多智能体产销协同系统

> **Deloitte 2026 Digital Camp Elite Challenge | Team D**

---

## English Version

### Overview

A **production-sales coordination system** powered by multi-agent architecture and Contract Net Protocol. Designed to detect market demand shocks (livestream events, competitor promotions, weather anomalies, supply disruptions) and automatically orchestrate 18 intelligent agents (1 Coordinator, 3 Sales, 10 Inventory, 3 Production, 1 Risk Observer) to negotiate and allocate inventory within **<2 hours**, targeting **>90% demand fulfillment** while minimizing procurement cost and stockout losses.

**Challenge Title**: 多智能体助力产销协同，提高供应链响应效率
*(Multi-Agent Systems for Production-Sales Coordination, Enhancing Supply Chain Response Efficiency)*

### Key Features

- **Real-Time Event Streaming** — SSE-based live agent negotiation visualization
- **Contract Net Protocol** — FIPA-ACL compliant multi-agent negotiation framework
- **Federated Forecasting** — Distributed time-series demand prediction with Laplace privacy (隐私保护)
- **Risk Assessment** — Multi-dimensional risk detection (shortage, overload, lead-time)
- **Responsive UI** — Desktop, tablet, and mobile layouts with live negotiation graph
- **Live Inventory Tracking** — Cross-run inventory state persistence (WMS simulation)
- **Scenario Simulation** — Pre-built scenarios (livestream, competitor, weather, supply shock)

### Tech Stack

**Backend:**
- FastAPI + LangGraph (agent orchestration)
- Prophet (forecasting) + OpenAI/Deepseek LLM (reasoning)
- FIPA-ACL protocol for agent communication

**Frontend:**
- Next.js 14 + React 18 + Tailwind CSS
- Zustand (state management) + Recharts (analytics)
- D3-style SVG animations for agent network visualization

### Architecture

```
┌─ Market Signal (外部信号)
│  └─ Coordinator (调度仲裁)
│     ├─ Sales Agents (华北/华东/华南) — demand forecast
│     ├─ Inventory Agents (×10 warehouses) — stock availability
│     └─ Production Agents (×3 factories) — manufacturing capacity
└─ Contract Net Protocol
   └─ Negotiation Results → Inventory Deduction → Next Run
```

### Quick Start

#### Backend
```bash
cd backend
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...  # or DEEPSEEK_API_KEY
uvicorn main:app --reload --port 8000
```

#### Frontend
```bash
cd frontend
npm install
npm run dev  # localhost:3000
```

Both servers must run simultaneously. Frontend calls `/api/*` endpoints on the backend.

### Core Workflow

1. **Signal Reception** — Market event triggers demand shock
2. **Federated Forecast** — 3 Sales agents predict regional demand (72h horizon)
3. **Shortage Detection** — Compare forecast vs. current stock
4. **CFP Broadcast** — Coordinator issues Call-For-Proposals
5. **Proposal Evaluation** — Inventory/Production agents bid with cost/time/delivery
6. **Greedy Auction** — Coordinator selects lowest-cost bids until shortage met or no more valid proposals
7. **Inventory Deduction** — Awarded quantities deducted from live WMS snapshot
8. **Result Visualization** — KPIs, fill rate, cost breakdown, avoided losses

### Scenarios

| Scenario | Signal | Region | Multiplier | Impact |
|----------|--------|--------|------------|--------|
| **Livestream Boom** | livestream | 华南 | 3.0× | SKU-A demand spike + factory fault (-30%) |
| **Competitor Promo** | competitor | 华东 | 2.0× | SKU-B承接溢出需求 |
| **Heat Wave** | weather | 华南 | 1.5× | Functional beverage demand surge |
| **Supply Shock** | supply_shock | — | 1.0× | Factory equipment failure (capacity −30%) |

### Testing

- **Scenario Trigger**: Select a scenario and click "▶ 触发协同"
- **Live Monitoring**: Watch the negotiation graph animate as events flow
- **Results Inspection**: KPI cards, fill-rate donut chart, bid comparison, Coordinator summary
- **Inventory Reset**: Use "重置库存" button to restore initial stock levels for replays

### File Structure

```
delotiee_agent/
├── backend/
│   ├── agents/
│   │   ├── coordinator_agent.py      # Contract Net Protocol, bid scoring
│   │   ├── inventory_agent.py        # Warehouse stock proposals
│   │   ├── production_agent.py       # Factory capacity proposals
│   │   ├── sales_agent.py            # Regional demand forecasting
│   │   ├── risk_agent.py             # Risk assessment (shortage/overload/lead-time)
│   │   └── market_signal_agent.py    # Signal injection
│   ├── graph/
│   │   ├── negotiation_graph.py      # LangGraph state machine (6 nodes)
│   │   ├── federated_forecast.py     # Distributed Prophet forecasts
│   │   └── contract_net.py           # FIPA-ACL message routing
│   ├── api/
│   │   └── routes.py                 # FastAPI endpoints + SSE stream
│   ├── data/
│   │   ├── generate_mock_data.py     # 180-day sales history, inventory, factory status
│   │   └── inventory_state.py        # Live WMS state + LRU cleanup
│   ├── llm/
│   │   └── client.py                 # OpenAI/Deepseek LLM wrapper
│   ├── protocols/
│   │   └── fipa_acl.py               # FIPA-ACL message definitions
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx              # Main layout (desktop/tablet/mobile)
│   │   │   ├── layout.tsx            # Next.js app router
│   │   │   └── globals.css           # Tailwind + animations
│   │   ├── components/
│   │   │   ├── NegotiationGraph.tsx  # Live agent network + SVG lines
│   │   │   ├── ScenarioPanel.tsx     # Signal input form
│   │   │   ├── ResultsPanel.tsx      # KPI cards + charts
│   │   │   ├── EventTimeline.tsx     # Event log stream
│   │   │   ├── AgentStatusPanel.tsx  # Agent activity indicator
│   │   │   └── InventoryWidget.tsx   # Stock level display
│   │   ├── store/
│   │   │   └── scenarioStore.ts      # Zustand store (events, results, status)
│   │   ├── hooks/
│   │   │   └── useScenario.ts        # SSE subscription + result fetch
│   │   └── lib/
│   │       └── agentEventMap.ts      # Event → node/edge animation mapping
│   ├── package.json
│   └── tsconfig.json
├── .env.example                       # Environment template
└── README.md                          # This file
```

### API Endpoints

**POST** `/api/run` — Trigger a scenario
```json
{
  "scenario_id": "main|competitor|weather|custom",
  "market_signals": [{"signal_type": "...", "region": "...", ...}]
}
```

**GET** `/api/events/{run_id}` — SSE stream of events (raw JSON)

**GET** `/api/result/{run_id}` — Final result with negotiation traces + KPIs

**GET** `/api/inventory/live` — Current WMS snapshot (after deductions)

**POST** `/api/inventory/reset` — Restore mock inventory defaults

---

## 中文版本

### 项目简介

基于多智能体架构和合约网协议（Contract Net Protocol）的**产销协同系统**。检测市场需求冲击（直播、竞品、气候、供给冲击），自动编排7个智能体（1个协调者、3个销售、10个库存、3个生产）进行谈判与库存分配，目标在**2小时内**完成协同，达到**90%以上**的需求满足率，同时最小化采购成本和缺货损失。

**赛题名称**: 多智能体助力产销协同，提高供应链响应效率

### 核心功能

- **实时事件流** — SSE 直播智能体谈判过程
- **合约网协议** — FIPA-ACL 规范的多智能体谈判框架
- **联邦预测** — 分布式时间序列预测 + 差分隐私
- **响应式 UI** — 桌面、平板、手机三端适配 + 谈判图实时动画
- **库存持久化** — 跨 run 库存扣减（WMS 模拟）
- **场景模拟** — 预设场景（直播爆单、竞品冲击、气候异常、供给冲击）

### 技术栈

**后端:**
- FastAPI + LangGraph（智能体编排）
- Prophet（预测）+ OpenAI/Deepseek LLM（推理）
- FIPA-ACL 智能体通信协议

**前端:**
- Next.js 14 + React 18 + Tailwind CSS
- Zustand（状态管理）+ Recharts（图表）
- D3 风格 SVG 动画（agent 网络可视化）

### 系统架构

```
市场信号 (外部信号)
  ↓
协调者 (Coordinator) — 合约网协议主持
  ├─ 销售员工 (Sales) — 区域需求预测
  ├─ 库存员工 (Inventory) — 仓库库存可用性
  └─ 生产员工 (Production) — 工厂产能
     ↓
  谈判结果 → 库存扣减 → 下次 run
```

### 快速开始

#### 后端
```bash
cd backend
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...  # 或 DEEPSEEK_API_KEY
uvicorn main:app --reload --port 8000
```

#### 前端
```bash
cd frontend
npm install
npm run dev  # 访问 localhost:3000
```

两个服务器需同时运行。前端调用后端的 `/api/*` 端点。

### 核心工作流

1. **信号接收** — 市场事件触发需求冲击
2. **联邦预测** — 3 个销售员工预测区域需求（72小时）
3. **缺货检测** — 对比预测 vs 当前库存
4. **发布招标（CFP）** — 协调者向所有库存、生产员工发布招标
5. **投标评估** — 库存/生产员工根据成本、时间、运输报价
6. **贪心拍卖** — 协调者选择最低成本投标直到缺货满足
7. **库存扣减** — 中标数量从 live WMS 快照扣减
8. **结果呈现** — KPI 卡片、满足率甜甜圈图、成本对比、避免损失

### 预设场景

| 场景 | 信号类型 | 区域 | 乘数 | 效果 |
|------|---------|------|------|------|
| **直播爆单** | livestream | 华南 | 3.0× | SKU-A 需求激增 + 广州厂故障（-30%） |
| **竞品冲击** | competitor | 华东 | 2.0× | SKU-B 承接溢出需求 |
| **高温预警** | weather | 华南 | 1.5× | 功能饮料需求上涨 |
| **供给冲击** | supply_shock | — | 1.0× | 工厂设备故障（产能 −30%） |

### 测试方式

- **触发场景** — 选择一个预设或自定义场景，点击"▶ 触发协同"
- **实时监控** — 观看谈判图动画，事件流实时更新
- **查看结果** — KPI、满足率、投标对比、协调摘要
- **重置库存** — 使用"重置库存"按钮恢复初始状态，可重复运行对比

### 核心代码

| 模块 | 文件 | 功能 |
|------|------|------|
| 协调者 | `backend/agents/coordinator_agent.py` | 合约网协议、投标评分 |
| 库存 | `backend/agents/inventory_agent.py` | 仓库库存投标 |
| 生产 | `backend/agents/production_agent.py` | 工厂产能投标 |
| 销售 | `backend/agents/sales_agent.py` | 区域需求预测 |
| 图执行 | `backend/graph/negotiation_graph.py` | LangGraph 6 节点状态机 |
| 前端主页 | `frontend/src/app/page.tsx` | 三端适配布局 |
| 谈判图 | `frontend/src/components/NegotiationGraph.tsx` | 智能体网络动画 |
| 结果面板 | `frontend/src/components/ResultsPanel.tsx` | KPI 卡片 + 图表 |

### API 端点

**POST** `/api/run` — 触发场景
```json
{
  "scenario_id": "main|competitor|weather|custom",
  "market_signals": [{"signal_type": "...", "region": "...", ...}]
}
```

**GET** `/api/events/{run_id}` — SSE 事件流

**GET** `/api/result/{run_id}` — 最终结果（谈判轨迹 + KPI）

**GET** `/api/inventory/live` — 当前 WMS 快照

**POST** `/api/inventory/reset` — 重置库存为初始状态

---

## Deployment | 部署

### Railway 部署

1. **创建 Railway 账户** → https://railway.app
2. **连接 GitHub 仓库**
3. **配置环境变量** (Railway Dashboard):
   ```
   OPENAI_API_KEY=sk-...
   ```
4. **后端部署** — 根目录选 Python，入口 `backend/main.py:app`
5. **前端部署** — Next.js 服务自动配置

---

---

## License

MIT License © 2026 Team D - Deloitte Digital Camp Elite Challenge
