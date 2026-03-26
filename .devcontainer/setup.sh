#!/usr/bin/env bash
set -euo pipefail

echo "=== [1/5] Starting PostgreSQL & Redis ==="
docker run -d --name postgres \
  -e POSTGRES_DB=llmplatform \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-devpassword}" \
  -p 5432:5432 \
  --restart unless-stopped \
  postgres:16-alpine

docker run -d --name redis \
  -p 6379:6379 \
  --restart unless-stopped \
  redis:7-alpine

echo "=== [2/5] Writing .env ==="
PG_PASS="${POSTGRES_PASSWORD:-devpassword}"
SK="${SECRET_KEY:-$(openssl rand -hex 32)}"
N8N_PASS="${N8N_PASSWORD:-admin123}"
N8N_CB_SECRET="$(openssl rand -hex 16)"

cat > .env << EOF
DEBUG=true
CORS_ORIGINS=http://localhost:3000

POSTGRES_PASSWORD=${PG_PASS}
DATABASE_URL=postgresql+asyncpg://postgres:${PG_PASS}@localhost:5432/llmplatform
DATABASE_URL_SYNC=postgresql://postgres:${PG_PASS}@localhost:5432/llmplatform

REDIS_URL=redis://localhost:6379/0

SECRET_KEY=${SK}
CREDENTIAL_ENCRYPTION_KEY=

STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRO_PRICE_ID=
STRIPE_ENTERPRISE_PRICE_ID=
FRONTEND_URL=http://localhost:3000

HF_TOKEN=
AGENT_LLM_PROVIDER=openai
AGENT_LLM_API_KEY=
AGENT_LLM_MODEL=gpt-4o-mini

N8N_WEBHOOK_URL=http://localhost:5678/webhook/autonomous-llm-builder
N8N_CALLBACK_SECRET=${N8N_CB_SECRET}
N8N_USER=admin
N8N_PASSWORD=${N8N_PASS}
EOF

echo "=== [3/5] Installing backend dependencies ==="
cd backend
python -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt
deactivate
cd ..

echo "=== [4/5] Installing frontend dependencies ==="
cd frontend
npm install
cd ..

echo "=== [5/5] Done! ==="
echo ""
echo "To start the app:"
echo "  Backend:  cd backend && source venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0"
echo "  Frontend: cd frontend && npm run dev"
echo ""
echo "Or use Docker Compose:"
echo "  docker compose up -d --build"
echo ""
echo "Ports: Frontend :3000 | Backend :8000 | n8n :5678"
