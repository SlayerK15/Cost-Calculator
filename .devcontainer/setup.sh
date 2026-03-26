#!/usr/bin/env bash
set -euo pipefail

# Run this manually after Codespace opens:
#   bash .devcontainer/setup.sh

echo "=== [1/3] Writing .env ==="
SK="$(openssl rand -hex 32)"

cat > backend/.env << EOF
DEBUG=true
CORS_ORIGINS=http://localhost:3000
DATABASE_URL=sqlite+aiosqlite:///./llmplatform.db
DATABASE_URL_SYNC=sqlite:///./llmplatform.db
REDIS_URL=
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
N8N_WEBHOOK_URL=
N8N_CALLBACK_SECRET=
EOF

cp backend/.env .env

echo "=== [2/3] Installing backend ==="
cd backend
pip install -r requirements.txt
cd ..

echo "=== [3/3] Installing frontend ==="
cd frontend
npm install
cd ..

echo ""
echo "Done! Start the app:"
echo "  Terminal 1: cd backend && uvicorn app.main:app --reload --host 0.0.0.0"
echo "  Terminal 2: cd frontend && npm run dev"
