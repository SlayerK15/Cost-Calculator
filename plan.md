# Phase 4 & 5 Implementation Plan

## Phase 4: Visual Pipeline Builder + Enhanced Dashboard

### 4A. Visual Pipeline Builder (Builder page enhancement)
Replace the current step-based builder wizard with an interactive visual pipeline canvas.

**Approach:** Build a custom node-graph UI using SVG + React (no new dependencies). Nodes are draggable cards connected by SVG path lines. This keeps the bundle small and avoids heavy deps like ReactFlow.

**Pipeline Nodes:**
- **Base Model** node (always present, start of pipeline)
- **LoRA Adapter** node (optional, connects from base model)
- **Model Merge** node (optional, connects 2+ models with method + weights)
- **Quantization** node (optional, connects from any model output)
- **Inference Config** node (always present, end of pipeline)

**Implementation:**
1. Create `frontend/src/components/pipeline/` with:
   - `PipelineCanvas.tsx` — SVG canvas with pan/zoom, renders nodes + connections
   - `PipelineNode.tsx` — Draggable card component (title, icon, mini-config, status)
   - `NodeEditor.tsx` — Side panel that opens when a node is clicked (shows full config form)
   - `ConnectionLine.tsx` — SVG bezier curves between node ports
2. Create `frontend/src/app/builder/[id]/pipeline/page.tsx` — New pipeline view page
3. Update `frontend/src/app/builder/[id]/page.tsx` — Add toggle between "Wizard" and "Pipeline" views
4. Backend: Add `PUT /builder/configs/{id}/pipeline` to save visual layout (node positions stored in existing `pipeline_json` column)

### 4B. Enhanced Dashboard with Recharts
Upgrade the current dashboard from a simple card list to a full analytics dashboard with charts (we already have `recharts` installed).

**Implementation:**
1. Rewrite `frontend/src/app/dashboard/page.tsx`:
   - **Top row:** 4 stat cards (active deploys, total requests, tokens, cost) — already exists, keep
   - **Charts row:** Add line charts (requests over time, cost over time) using Recharts
   - **Deployments table:** Replace card list with a proper table with sorting + status filters
   - **Cost breakdown:** Pie chart showing cost per deployment
2. Create `backend/app/api/analytics.py`:
   - `GET /analytics/summary` — Aggregated stats across all deployments
   - `GET /analytics/usage-series?days=30` — Time-series usage data for charts
   - `GET /analytics/cost-breakdown` — Per-deployment cost breakdown
3. Register router in `main.py`

### 4C. Auto-scaling improvements
Enhance the managed deployment auto-scaling with simulated scaling events.

1. Update `monitoring_service.py` — Add `simulate_scaling_event()` that returns scaling decisions based on current GPU utilization vs target
2. Update `GET /managed/{id}/metrics` — Include `scaling_events` in response (list of recent scale up/down events with timestamps)
3. Update `frontend/src/app/managed/[id]/page.tsx` — Add scaling events timeline below charts

---

## Phase 5: Playground + Cost Alerts + Landing Page Polish

### 5A. Model Playground / Test Endpoint
Let users test their model configs with a chat-like interface before deploying.

**Implementation:**
1. Create `frontend/src/app/playground/page.tsx`:
   - Model config selector dropdown
   - Chat-style interface (message input + response display)
   - Simulated response with token count, latency estimate, cost-per-request estimate
   - "Deploy this model" CTA button
2. Create `backend/app/api/playground.py`:
   - `POST /playground/simulate` — Takes config_id + prompt, returns simulated response with metrics (estimated tokens, latency based on model size, cost projection)
3. Register router, add to navbar

### 5B. Cost Alerts & Budget Tracking
Let enterprise users set cost budgets and get threshold alerts.

**Implementation:**
1. Add `CostAlert` model in `models.py`:
   - `managed_deployment_id`, `monthly_budget_usd`, `alert_threshold_pct` (e.g. 80%), `alert_triggered`, `alert_triggered_at`
2. Create `backend/app/api/alerts.py`:
   - `POST /alerts/create` — Create cost alert for a managed deployment
   - `GET /alerts/list` — List all alerts with current spend vs budget
   - `PUT /alerts/{id}` — Update alert thresholds
   - `DELETE /alerts/{id}` — Remove alert
3. Create `frontend/src/app/settings/alerts/page.tsx`:
   - Alert management UI with progress bars showing spend vs budget
   - Visual indicators: green (<60%), yellow (60-80%), red (>80%)
4. Update `frontend/src/app/managed/[id]/page.tsx` — Show budget status bar in deployment detail

### 5C. Landing Page + Polish
Modernize the home page and add overall platform polish.

**Implementation:**
1. Rewrite `frontend/src/app/page.tsx`:
   - Hero section with animated gradient background
   - Platform stats counter (e.g. "X models configured, Y deployments")
   - Workflow diagram: Calculator → Builder → Deploy → Monitor (horizontal pipeline visual)
   - Testimonial/social proof placeholder section
   - Comparison table (Self-host vs API providers vs Our Platform)
   - Updated CTA with tier-specific buttons
2. Add tier badge to Navbar (shows FREE/PRO/ENTERPRISE pill next to user)
3. Add breadcrumb navigation to inner pages

---

## File Summary

**New files to create:**
- `frontend/src/components/pipeline/PipelineCanvas.tsx`
- `frontend/src/components/pipeline/PipelineNode.tsx`
- `frontend/src/components/pipeline/NodeEditor.tsx`
- `frontend/src/components/pipeline/ConnectionLine.tsx`
- `frontend/src/app/builder/[id]/pipeline/page.tsx`
- `backend/app/api/analytics.py`
- `frontend/src/app/playground/page.tsx`
- `backend/app/api/playground.py`
- `backend/app/api/alerts.py`
- `frontend/src/app/settings/alerts/page.tsx`

**Files to modify:**
- `frontend/src/app/builder/[id]/page.tsx` — Add pipeline toggle
- `frontend/src/app/dashboard/page.tsx` — Full rewrite with Recharts
- `frontend/src/app/managed/[id]/page.tsx` — Scaling events + budget bar
- `frontend/src/app/page.tsx` — Landing page rewrite
- `frontend/src/components/Navbar.tsx` — Add Playground link + tier badge
- `frontend/src/types/index.ts` — New types
- `frontend/src/lib/api.ts` — New API functions
- `backend/app/main.py` — Register new routers
- `backend/app/models/models.py` — CostAlert model
- `backend/app/services/monitoring_service.py` — Scaling events
