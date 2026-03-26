#!/usr/bin/env bash
set -euo pipefail

# Quick start script for Codespaces / devcontainer
# Starts backend + frontend with hot-reload

# Ensure .env exists
if [ ! -f .env ]; then
  echo "No .env found — running setup first..."
  bash .devcontainer/setup.sh
fi

# Source .env
set -a; source .env; set +a

# Ensure Postgres & Redis are running
docker start postgres 2>/dev/null || docker run -d --name postgres \
  -e POSTGRES_DB=llmplatform -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  -p 5432:5432 postgres:16-alpine

docker start redis 2>/dev/null || docker run -d --name redis \
  -p 6379:6379 redis:7-alpine

echo "Waiting for Postgres..."
for i in {1..30}; do
  docker exec postgres pg_isready -U postgres &>/dev/null && break
  sleep 1
done

echo "Starting backend..."
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

echo "Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "========================================="
echo " App running in Codespaces!"
echo "========================================="
echo " Frontend: port 3000 (check Ports tab)"
echo " Backend:  port 8000"
echo " n8n:      port 5678 (start separately)"
echo ""
echo "Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
