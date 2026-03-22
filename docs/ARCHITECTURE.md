# LLM Cloud Cost & Deployment Platform — Architecture Documentation

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Component Architecture](#component-architecture)
4. [Data Flow](#data-flow)
5. [Backend Services](#backend-services)
6. [Frontend Architecture](#frontend-architecture)
7. [Infrastructure & Deployment](#infrastructure--deployment)
8. [Security Architecture](#security-architecture)
9. [API Reference](#api-reference)
10. [Database Schema](#database-schema)
11. [Testing Strategy](#testing-strategy)
12. [n8n Workflow Pipeline](#n8n-workflow-pipeline)
13. [Infrastructure Agent](#infrastructure-agent)

---

## System Overview

The LLM Cloud Cost & Deployment Platform is a full-stack application that helps users:

- **Estimate costs** for self-hosting open-source LLM models on AWS, GCP, and Azure
- **Compare costs** across cloud providers and against API providers (OpenAI, Anthropic, etc.)
- **Generate deployment files** (Dockerfile, Kubernetes, Terraform, CloudFormation, Pulumi)
- **Build custom models** via LoRA adapters, model merging, and quantization
- **Deploy and manage** LLM infrastructure with autoscaling and monitoring
- **Automate fine-tuning** via n8n workflow pipelines (domain search → data collection → training → deployment)
- **Chat with an AI agent** that can answer cost questions and generate infrastructure

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.11+, async SQLAlchemy |
| Database | SQLite (dev) / PostgreSQL (prod) via aiosqlite/asyncpg |
| Auth | JWT (HS256), bcrypt password hashing |
| IaC | Terraform, CloudFormation, Pulumi, Kubernetes YAML |
| Orchestration | n8n (37-node workflow), Docker Compose, Kubernetes |
| AI Agent | OpenAI / Anthropic API with function calling |
| Testing | pytest, pytest-asyncio, httpx.AsyncClient |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js 14)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────┐ │
│  │  Cost     │ │  Model   │ │  Deploy  │ │ Workflow │ │ Infra │ │
│  │Calculator │ │  Builder │ │  Manager │ │ Pipeline │ │ Agent │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬───┘ │
│       │             │            │             │           │     │
│       └─────────────┴────────────┴─────────────┴───────────┘     │
│                              │                                    │
│                    ┌─────────┴─────────┐                         │
│                    │   API Client       │                         │
│                    │   (fetch + SSE)    │                         │
│                    └─────────┬─────────┘                         │
└──────────────────────────────┼───────────────────────────────────┘
                               │ HTTP/SSE
                    ┌──────────┴──────────┐
                    │   NGINX / Ingress    │
                    │   (Rate Limit, TLS)  │
                    └──────────┬──────────┘
                               │
┌──────────────────────────────┼───────────────────────────────────┐
│                     BACKEND (FastAPI)                              │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    API Layer (Routers)                        │  │
│  │  /auth  /models  /estimate  /deploy  /builder  /managed     │  │
│  │  /workflow  /agent  /infra  /compare  /share  /recommend    │  │
│  │  /pricing  /subscription  /analytics  /alerts  /credentials │  │
│  └────────────────────────┬────────────────────────────────────┘  │
│                           │                                        │
│  ┌────────────────────────┴────────────────────────────────────┐  │
│  │                   Service Layer                              │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐              │  │
│  │  │ Cost Engine │ │ Deployment │ │   Agent    │              │  │
│  │  │ (Calculator │ │ Generator  │ │  Service   │              │  │
│  │  │  GPU Catalog│ │ (TF/CFN/   │ │ (OpenAI/   │              │  │
│  │  │  Optimizer) │ │  Pulumi/K8s│ │  Anthropic)│              │  │
│  │  └────────────┘ └────────────┘ └────────────┘              │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐              │  │
│  │  │ Recommender│ │ Forecaster │ │Infra Agent │              │  │
│  │  │ (Model     │ │ (Linear    │ │(Multi-cloud│              │  │
│  │  │  Matching) │ │  Regression│ │ IaC Gen)   │              │  │
│  │  └────────────┘ └────────────┘ └────────────┘              │  │
│  │  ┌────────────┐ ┌────────────┐                              │  │
│  │  │ Credential │ │   Price    │                              │  │
│  │  │  Service   │ │  Fetcher   │                              │  │
│  │  │ (Fernet)   │ │ (Periodic) │                              │  │
│  │  └────────────┘ └────────────┘                              │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                           │                                        │
│              ┌────────────┴────────────┐                          │
│              │    Database (SQLAlchemy) │                          │
│              │    SQLite / PostgreSQL   │                          │
│              └─────────────────────────┘                          │
└───────────────────────────────────────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │   n8n Workflow       │
                    │   (37-node pipeline) │
                    │   Search → Clean →   │
                    │   Train → Deploy     │
                    └─────────────────────┘
```

---

## Component Architecture

### Backend Structure

```
backend/
├── app/
│   ├── api/                    # FastAPI routers (18 routers)
│   │   ├── auth.py             # Register, login, JWT
│   │   ├── models_api.py       # Popular models, HF import, custom upload
│   │   ├── estimate.py         # Cost estimation (public + authenticated)
│   │   ├── deploy.py           # Config generation, bundle download
│   │   ├── builder.py          # Model configs, specs, versioning
│   │   ├── managed.py          # Cloud deployment lifecycle
│   │   ├── workflow.py         # n8n workflow trigger + callbacks
│   │   ├── agent.py            # AI chatbot (SSE streaming)
│   │   ├── infra.py            # Infrastructure agent (multi-cloud IaC)
│   │   ├── compare.py          # Multi-model comparison
│   │   ├── share.py            # Estimate sharing (public links)
│   │   ├── recommend.py        # Model recommendations
│   │   ├── pricing.py          # Live pricing status + webhook
│   │   ├── subscription.py     # Stripe billing + tier management
│   │   ├── analytics.py        # Usage stats + cost breakdown
│   │   ├── alerts.py           # Cost alert CRUD
│   │   ├── credentials.py      # Cloud credential management
│   │   ├── chat.py             # Inference chat endpoint
│   │   └── playground.py       # Model playground
│   ├── core/
│   │   ├── config.py           # Pydantic settings (env-based)
│   │   ├── database.py         # Async SQLAlchemy engine + session
│   │   └── security.py         # JWT, bcrypt, auth dependencies
│   ├── models/
│   │   └── models.py           # SQLAlchemy ORM models
│   ├── schemas/
│   │   ├── models.py           # Pydantic request/response schemas
│   │   ├── agent.py            # Agent chat schemas
│   │   ├── compare.py          # Comparison schemas
│   │   ├── infra.py            # Infrastructure agent schemas
│   │   ├── optimizer.py        # Optimization schemas
│   │   ├── recommend.py        # Recommendation schemas
│   │   ├── share.py            # Sharing schemas
│   │   └── workflow.py         # Workflow schemas
│   └── services/
│       ├── cost_engine/
│       │   ├── calculator.py   # VRAM calculation + GPU matching + cost
│       │   └── gpu_catalog.py  # GPU specs (T4, A10G, A100, H100, L4)
│       ├── deployment_generator.py  # Dockerfile, K8s, TF, CFN generation
│       ├── infra_agent.py      # Multi-cloud IaC agent + search
│       ├── agent_service.py    # AI chatbot orchestration
│       ├── agent_tools.py      # Tool definitions + executors
│       ├── recommender.py      # Model recommendation engine
│       ├── optimizer.py        # Cost optimization suggestions
│       ├── forecaster.py       # Linear regression cost forecasting
│       ├── credential_service.py  # Fernet encryption for cloud creds
│       └── price_fetcher.py    # Periodic GPU/API price updates
└── tests/                      # 160+ tests (pytest-asyncio)
```

### Frontend Structure

```
frontend/src/
├── app/                        # Next.js App Router pages
│   ├── page.tsx                # Home / landing
│   ├── auth/page.tsx           # Login / register
│   ├── estimate/page.tsx       # Cost calculator
│   ├── compare/page.tsx        # Multi-model comparison
│   ├── recommend/page.tsx      # Model recommendations
│   ├── infra/page.tsx          # Infrastructure agent
│   ├── workflow/page.tsx       # n8n workflow trigger + status
│   ├── builder/page.tsx        # Model builder
│   ├── deploy/page.tsx         # Deployment configs
│   ├── managed/page.tsx        # Managed deployments
│   ├── dashboard/page.tsx      # Analytics dashboard
│   └── share/[token]/page.tsx  # Shared estimate viewer
├── components/
│   ├── Navbar.tsx              # Navigation (public + auth routes)
│   ├── CostBreakdown.tsx       # Cost estimate card
│   ├── APIProviderComparison.tsx  # API vs self-hosted
│   ├── OptimizationPanel.tsx   # Cost optimization suggestions
│   └── AgentChatWidget.tsx     # Floating AI chatbot
├── lib/
│   └── api.ts                  # API client (fetch + SSE)
├── types/
│   └── index.ts                # TypeScript interfaces
└── contexts/                   # React context providers
```

---

## Data Flow

### Cost Estimation Flow

```
User Input (model, provider, precision, QPS, hours)
        │
        ▼
┌─────────────────┐
│  Cost Engine     │
│  1. VRAM calc    │──▶ parameters × bytes_per_param + KV cache overhead
│  2. GPU match    │──▶ smallest GPU(s) that fit VRAM requirement
│  3. Instance map │──▶ cloud-specific instance type
│  4. Cost calc    │──▶ compute + storage + bandwidth + idle costs
│  5. Scaling      │──▶ 1x, 2x, 5x, 10x replica scenarios
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  API Comparison  │──▶ Compare vs OpenAI, Anthropic, Google, Mistral
└────────┬────────┘
         │
         ▼
    Response: CostEstimate + APIProviderComparison
```

### Infrastructure Agent Flow

```
User Input (model, provider, IaC language, region)
        │
        ▼
┌──────────────────────┐
│  Infra Agent Service  │
│  1. Resolve GPU/inst  │──▶ Cost engine finds optimal GPU + instance
│  2. Generate files    │
│     ├── Dockerfile    │──▶ vLLM-based with model config
│     ├── K8s YAML      │──▶ Deployment + Service + HPA
│     ├── IaC config    │──▶ Terraform / CloudFormation / Pulumi
│     ├── CI/CD         │──▶ GitHub Actions pipeline
│     ├── Monitoring    │──▶ Prometheus + Grafana (optional)
│     └── Quickstart    │──▶ Step-by-step CLI instructions
└──────────────────────┘
```

### n8n Workflow Pipeline Flow

```
User triggers workflow (domain, use_case, base_model)
        │
        ▼
┌──────────────────────────────────────────────────────┐
│  n8n 37-Node Pipeline                                 │
│                                                       │
│  1. Webhook ──▶ Receive trigger from platform         │
│  2. Normalize Input                                   │
│  3. List Available Models ──▶ Ollama API              │
│  4. Select Base Model                                 │
│  5. Pull Base Model ──▶ Ollama pull                   │
│  6. Search Planner ──▶ Generate search queries        │
│  7. Search Web ──▶ DuckDuckGo / Brave                │
│  8. Fetch Pages ──▶ HTTP requests                     │
│  9. Clean Content ──▶ Strip HTML, normalize           │
│  10. Chunk Data ──▶ Split into training samples       │
│  11. Format as QA pairs                               │
│  12. Train with LoRA ──▶ Ollama create               │
│  13. Register in Ollama                               │
│  14. Callback ──▶ Notify platform of completion       │
└──────────────────────────────────────────────────────┘
```

---

## Backend Services

### Cost Engine (`services/cost_engine/`)

The cost engine calculates deployment costs using:

- **VRAM Calculation**: `parameters_billion × bytes_per_param + KV_cache_overhead`
  - FP16: 2 bytes/param, BF16: 2 bytes, INT8: 1 byte, INT4: 0.5 bytes
  - KV cache adds ~10-30% overhead depending on context length
- **GPU Matching**: Selects the smallest GPU(s) that satisfy VRAM requirement
- **Instance Mapping**: Maps GPU to provider-specific instance types
- **Cost Calculation**: `(hourly_rate × hours_per_day × days_per_month) + storage + bandwidth`

### GPU Catalog

| GPU | VRAM | FP16 TFLOPS | Memory BW |
|-----|------|-------------|-----------|
| T4 | 16 GB | 65 | 300 GB/s |
| A10G | 24 GB | 125 | 600 GB/s |
| L4 | 24 GB | 121 | 300 GB/s |
| A100 40GB | 40 GB | 312 | 2039 GB/s |
| A100 80GB | 80 GB | 312 | 2039 GB/s |
| H100 | 80 GB | 990 | 3350 GB/s |

### Infrastructure Agent (`services/infra_agent.py`)

Generates deployment files for multiple IaC languages:

| IaC Language | Providers | Files Generated |
|-------------|-----------|-----------------|
| Terraform | AWS, GCP, Azure | main.tf (VPC, EKS/GKE/AKS, ECR/GAR/ACR, S3/GCS/Blob) |
| CloudFormation | AWS only | cloudformation.yaml (EKS, ECR, S3, IAM, VPC) |
| Pulumi | AWS, GCP, Azure | __main__.py + Pulumi.yaml + requirements.txt |
| Kubernetes | All | kubernetes.yaml (Deployment, Service, HPA) |

All options also generate: Dockerfile, CI/CD pipeline, monitoring YAML, quickstart script.

### Agent Service (`services/agent_service.py`)

AI chatbot with function calling support:

- **Online mode**: Calls OpenAI or Anthropic API with tool definitions
- **Offline mode**: Pattern-matches user intent and calls tools directly
- **Tools**: `estimate_cost`, `compare_providers`, `recommend_model`, `search_models`, `get_gpu_info`, `generate_infra`, `search_infra`

### Recommender (`services/recommender.py`)

Matches models to use cases using a catalog of 15+ open-source models with quality tags, then filters by budget using the cost engine.

### Optimizer (`services/optimizer.py`)

Suggests cost optimizations: precision reduction, spot instances, scheduled scaling, reserved instances, smaller context windows.

### Forecaster (`services/forecaster.py`)

Linear regression on historical usage metrics to project 30-day costs.

---

## Security Architecture

### Authentication & Authorization

- **JWT tokens** with HS256 signing, 8-hour expiry
- **bcrypt** password hashing (12 rounds)
- **Three-tier access**: Free → Pro → Enterprise
- **Production secret validation**: Rejects insecure defaults when `DEBUG=False`

### Production Hardening

- **Security headers**: X-Content-Type-Options, X-Frame-Options, HSTS, Referrer-Policy
- **CORS**: Restricted origins (configurable via `CORS_ORIGINS`)
- **Rate limiting**: NGINX ingress at 10 rps per IP
- **Timing-safe comparisons**: `hmac.compare_digest` for webhook/callback secrets
- **Credential encryption**: Fernet symmetric encryption for cloud credentials
- **API docs disabled** in production (`docs_url=None`)

### Kubernetes Security

- **Network Policies**: Default deny all, explicit per-service allowlists
- **RBAC**: Dedicated ServiceAccounts per service, minimal permissions
- **Pod Security**: Non-root containers, read-only root filesystem, seccomp profiles
- **Secrets**: In-memory generation via `deploy.sh`, External Secrets Operator for vault integration
- **Redis**: Password-authenticated, dangerous commands disabled
- **PostgreSQL**: scram-sha-256 auth, connection logging, non-root user

---

## API Reference

### Public Endpoints (No Auth)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/estimate/public` | Estimate cost for a model |
| POST | `/api/estimate/public/compare` | Compare across providers |
| POST | `/api/estimate/public/compare-api-providers` | Compare vs API providers |
| GET | `/api/models/popular` | List popular models |
| GET | `/api/pricing/status` | Live pricing status |
| POST | `/api/compare/models` | Multi-model comparison |
| POST | `/api/recommend/models` | Model recommendations |
| POST | `/api/agent/chat` | AI chatbot (SSE) |
| POST | `/api/agent/chat/sync` | AI chatbot (non-streaming) |
| POST | `/api/infra/generate` | Generate deployment files |
| POST | `/api/infra/search` | Search cloud infrastructure |
| GET | `/api/share/{token}` | View shared estimate |

### Authenticated Endpoints

| Method | Path | Tier | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | — | Create account |
| POST | `/api/auth/login` | — | Get JWT token |
| GET | `/api/auth/me` | Free | User profile |
| POST | `/api/estimate/` | Free | Estimate (with model_id) |
| POST | `/api/deploy/generate-configs` | Pro | Generate deploy bundle |
| GET | `/api/deploy/{id}/bundle` | Pro | Download config ZIP |
| POST | `/api/builder/configs` | Pro | Create model config |
| POST | `/api/managed/deploy` | Enterprise | Deploy to cloud |
| POST | `/api/credentials/create` | Enterprise | Add cloud credentials |
| POST | `/api/workflow/trigger` | Free | Trigger n8n pipeline |

---

## Database Schema

### Core Tables

```
┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐
│    User       │    │    LLMModel       │    │   Deployment     │
├──────────────┤    ├──────────────────┤    ├──────────────────┤
│ id (UUID)     │    │ id (UUID)         │    │ id (UUID)         │
│ email         │◄───│ user_id           │◄───│ model_id          │
│ hashed_pass   │    │ name              │    │ user_id           │
│ tier          │    │ source (hf/custom)│    │ cloud_provider    │
│ full_name     │    │ parameters_billion│    │ status            │
│ stripe_*      │    │ precision         │    │ instance_type     │
│ created_at    │    │ context_length    │    │ gpu_type/count    │
└──────────────┘    │ architecture      │    │ region            │
       │            └──────────────────┘    │ endpoint_url      │
       │                                     │ total_cost        │
       │            ┌──────────────────┐    └──────────────────┘
       │            │  ModelConfig      │
       ├───────────▶├──────────────────┤    ┌──────────────────┐
       │            │ id (UUID)         │    │ ManagedDeployment │
       │            │ user_id           │    ├──────────────────┤
       │            │ base_model_hf_id  │    │ id (UUID)         │
       │            │ adapter_hf_id     │    │ deployment_id     │
       │            │ merge_method      │    │ credential_id     │
       │            │ quantization      │    │ status            │
       │            │ system_prompt     │    │ autoscaling_*     │
       │            │ version           │    │ health_status     │
       │            └──────────────────┘    │ total_cost        │
       │                                     └──────────────────┘
       │            ┌──────────────────┐
       ├───────────▶│  WorkflowRun      │    ┌──────────────────┐
       │            ├──────────────────┤    │ CloudCredential   │
       │            │ id (UUID)         │    ├──────────────────┤
       │            │ user_id           │    │ id (UUID)         │
       │            │ status            │    │ user_id           │
       │            │ domain            │    │ provider          │
       │            │ use_case          │    │ label             │
       │            │ n8n_execution_id  │    │ encrypted_creds   │
       │            │ result_snapshot   │    │ status            │
       │            └──────────────────┘    └──────────────────┘
       │
       │            ┌──────────────────┐    ┌──────────────────┐
       ├───────────▶│ SavedEstimate     │    │  SharedEstimate   │
       │            │ CostAlert         │    │  (public, no auth)│
       └───────────▶│ UsageRecord       │    └──────────────────┘
```

---

## Testing Strategy

### Test Structure

```
backend/tests/
├── conftest.py              # Fixtures: async DB, test client, auth helpers
├── test_auth.py             # Register, login, /me, token validation
├── test_models.py           # Popular models, HF import, custom upload
├── test_estimate.py         # Public estimate, compare, optimize
├── test_deploy.py           # Config generation, bundle download
├── test_builder.py          # Model configs, specs, versioning
├── test_managed.py          # Deploy, metrics, scale, forecast
├── test_compare.py          # Multi-model comparison
├── test_share.py            # Create share, get shared
├── test_recommend.py        # Model recommendations
├── test_agent.py            # Agent chat (sync + SSE)
├── test_workflow.py         # Trigger, runs, callbacks
├── test_infra.py            # Infra agent (27 tests)
├── test_credentials.py      # Cloud credentials
├── test_analytics.py        # Usage stats
├── test_alerts.py           # Cost alerts
├── test_pricing.py          # Pricing status
└── test_services/           # Unit tests for services
    ├── test_calculator.py
    ├── test_recommender.py
    ├── test_optimizer.py
    ├── test_forecaster.py
    ├── test_agent_tools.py
    └── test_deployment_gen.py
```

### Test Patterns

- **pytest + pytest-asyncio** with `asyncio_mode = auto`
- **In-memory SQLite** via `aiosqlite` for test isolation
- **httpx.AsyncClient** with `ASGITransport` for integration tests
- **Fixture-based auth**: `free_user`, `pro_user`, `enterprise_user`
- **15-second timeout** per test to catch hangs
- **Coverage**: 160+ tests across all 19 routers and 6 services

### Running Tests

```bash
cd backend
pip install pytest pytest-asyncio httpx pytest-timeout
python -m pytest tests/ -v --timeout=15
```

---

## Infrastructure & Deployment

### Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
cp ../.env.example .env  # DEBUG=true
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev  # port 3000
```

### Docker Compose

```bash
docker-compose up --build
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
# n8n: http://localhost:5678
```

### Kubernetes Production

```bash
cd k8s
./deploy.sh              # Full deployment
./deploy.sh --dry-run    # Preview changes
./deploy.sh --secrets-only  # Update secrets only
```

### K8s Manifest Summary

| File | Purpose |
|------|---------|
| `namespace.yaml` | `llm-platform` namespace |
| `configmap.yaml` | Non-secret configuration |
| `secrets.yaml` | Template + instructions (use deploy.sh or ESO) |
| `external-secrets.yaml` | External Secrets Operator integration |
| `rbac.yaml` | ServiceAccounts + Roles |
| `networkpolicy.yaml` | Zero-trust pod networking |
| `backend.yaml` | Backend deployment + service |
| `frontend.yaml` | Frontend deployment + service |
| `postgres.yaml` | PostgreSQL StatefulSet |
| `redis.yaml` | Redis deployment (password-auth) |
| `n8n.yaml` | n8n workflow engine |
| `ingress.yaml` | NGINX ingress with TLS + rate limiting |
| `hpa.yaml` | Horizontal Pod Autoscalers |
| `pdb.yaml` | Pod Disruption Budgets |
| `backup-cronjob.yaml` | Daily PostgreSQL backups |
| `deploy.sh` | One-command deployment script |

---

## n8n Workflow Pipeline

The autonomous domain LLM builder is a 37-node n8n workflow that:

1. **Receives trigger** from the platform (domain, use_case, base_model)
2. **Selects base model** from available Ollama models
3. **Plans search queries** for the target domain
4. **Searches the web** (DuckDuckGo/Brave) for domain-specific content
5. **Fetches and cleans** web pages (HTML stripping, deduplication)
6. **Chunks content** into training-sized samples
7. **Formats as QA pairs** for instruction tuning
8. **Fine-tunes via LoRA** using Ollama's create API
9. **Registers the model** in Ollama for serving
10. **Callbacks** the platform with results and status updates

Data pipeline: Raw web data → Cleaned text → Chunked samples → QA pairs → LoRA training data

Training data is stored separately from raw data — raw content is cleaned and transformed before being used for fine-tuning.

---

## Infrastructure Agent

The Infrastructure Agent generates production-ready deployment files for any combination of:

- **Cloud Providers**: AWS (EKS), GCP (GKE), Azure (AKS)
- **IaC Languages**: Terraform, CloudFormation, Pulumi, Kubernetes-only
- **Features**: Autoscaling, monitoring (Prometheus/Grafana), CI/CD pipelines

### Supported Output Files

| File | Description |
|------|-------------|
| `Dockerfile` | vLLM-based container with model config |
| `kubernetes.yaml` | Deployment + Service + HPA with GPU scheduling |
| `main.tf` | Terraform: VPC, K8s cluster, registry, storage |
| `cloudformation.yaml` | AWS-native: EKS, ECR, S3, IAM, VPC |
| `__main__.py` | Pulumi Python: type-safe IaC |
| `monitoring.yaml` | Prometheus ServiceMonitor + Grafana dashboard |
| `.github/workflows/deploy.yaml` | CI/CD pipeline |
| `QUICKSTART.sh` | Step-by-step deployment instructions |

### Agent Tools (for AI chatbot)

The infra agent is also available as tools for the AI chatbot:
- `generate_infra` — Generate deployment files via natural language
- `search_infra` — Search GPU instances, pricing, best practices

### API Endpoints

```
POST /api/infra/generate  — Generate deployment files
POST /api/infra/search    — Search cloud infrastructure
```
