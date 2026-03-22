#!/usr/bin/env bash
# ============================================================
# LLM Cloud Platform — Kubernetes Deployment Script
#
# Usage:
#   ./deploy.sh                    # Full deploy (prompts for missing secrets)
#   ./deploy.sh --secrets-only     # Only create/update secrets
#   ./deploy.sh --dry-run          # Show what would be applied
#
# Prerequisites:
#   - kubectl configured for your cluster
#   - Docker images pushed to your registry
#   - (Optional) External Secrets Operator installed
#
# This script NEVER stores secrets on disk. All secrets are
# generated in-memory and piped directly to kubectl.
# ============================================================

set -euo pipefail

NAMESPACE="llm-platform"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=""
SECRETS_ONLY=false

# ── Parse args ──
for arg in "$@"; do
  case "$arg" in
    --dry-run)     DRY_RUN="--dry-run=client" ;;
    --secrets-only) SECRETS_ONLY=true ;;
    --help|-h)
      echo "Usage: $0 [--secrets-only] [--dry-run]"
      exit 0
      ;;
  esac
done

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  LLM Cloud Platform — Kubernetes Deployment            ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Create namespace ──
echo "→ Creating namespace: ${NAMESPACE}"
kubectl apply -f "${SCRIPT_DIR}/namespace.yaml" ${DRY_RUN}
echo ""

# ── Step 2: Secrets (generated in-memory, never written to disk) ──
echo "→ Checking secrets..."
if ! kubectl get secret llm-platform-secrets -n "${NAMESPACE}" &>/dev/null || [ -n "${FORCE_SECRETS:-}" ]; then
  echo "  Generating new secrets (values stay in-memory only)..."

  SECRET_KEY="${SECRET_KEY:-$(openssl rand -hex 32)}"
  POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(openssl rand -hex 16)}"
  REDIS_PASSWORD="${REDIS_PASSWORD:-$(openssl rand -hex 16)}"
  CREDENTIAL_ENCRYPTION_KEY="${CREDENTIAL_ENCRYPTION_KEY:-$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())' 2>/dev/null || echo "GENERATE_ME")}"
  N8N_CALLBACK_SECRET="${N8N_CALLBACK_SECRET:-$(openssl rand -hex 16)}"
  N8N_BASIC_AUTH_PASSWORD="${N8N_BASIC_AUTH_PASSWORD:-$(openssl rand -hex 12)}"

  # These should be provided by the operator; default to empty
  STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY:-}"
  STRIPE_WEBHOOK_SECRET="${STRIPE_WEBHOOK_SECRET:-}"
  STRIPE_PRO_PRICE_ID="${STRIPE_PRO_PRICE_ID:-}"
  STRIPE_ENTERPRISE_PRICE_ID="${STRIPE_ENTERPRISE_PRICE_ID:-}"
  HF_TOKEN="${HF_TOKEN:-}"
  AGENT_LLM_API_KEY="${AGENT_LLM_API_KEY:-}"

  kubectl create secret generic llm-platform-secrets \
    --namespace="${NAMESPACE}" \
    --from-literal=SECRET_KEY="${SECRET_KEY}" \
    --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
    --from-literal=REDIS_PASSWORD="${REDIS_PASSWORD}" \
    --from-literal=CREDENTIAL_ENCRYPTION_KEY="${CREDENTIAL_ENCRYPTION_KEY}" \
    --from-literal=N8N_CALLBACK_SECRET="${N8N_CALLBACK_SECRET}" \
    --from-literal=N8N_BASIC_AUTH_PASSWORD="${N8N_BASIC_AUTH_PASSWORD}" \
    --from-literal=STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY}" \
    --from-literal=STRIPE_WEBHOOK_SECRET="${STRIPE_WEBHOOK_SECRET}" \
    --from-literal=STRIPE_PRO_PRICE_ID="${STRIPE_PRO_PRICE_ID}" \
    --from-literal=STRIPE_ENTERPRISE_PRICE_ID="${STRIPE_ENTERPRISE_PRICE_ID}" \
    --from-literal=HF_TOKEN="${HF_TOKEN}" \
    --from-literal=AGENT_LLM_API_KEY="${AGENT_LLM_API_KEY}" \
    --save-config ${DRY_RUN} \
    -o yaml | kubectl apply -f - ${DRY_RUN}

  echo ""
  echo "  ┌─────────────────────────────────────────────────────┐"
  echo "  │  IMPORTANT: Save these credentials securely NOW.    │"
  echo "  │  They are NOT stored on disk anywhere.              │"
  echo "  │                                                     │"
  echo "  │  Postgres password: ${POSTGRES_PASSWORD}            │"
  echo "  │  Redis password:    ${REDIS_PASSWORD}               │"
  echo "  │  n8n password:      ${N8N_BASIC_AUTH_PASSWORD}      │"
  echo "  │                                                     │"
  echo "  │  To retrieve later:                                 │"
  echo "  │  kubectl get secret llm-platform-secrets \\          │"
  echo "  │    -n ${NAMESPACE} -o jsonpath='{.data.KEY}'\\      │"
  echo "  │    | base64 -d                                      │"
  echo "  └─────────────────────────────────────────────────────┘"
  echo ""
else
  echo "  Secrets already exist. Set FORCE_SECRETS=1 to regenerate."
fi

if [ "${SECRETS_ONLY}" = true ]; then
  echo "Done (secrets only)."
  exit 0
fi

# ── Step 3: ConfigMap ──
echo "→ Applying ConfigMap..."
kubectl apply -f "${SCRIPT_DIR}/configmap.yaml" ${DRY_RUN}

# ── Step 4: RBAC ──
echo "→ Applying RBAC (ServiceAccounts, Roles, RoleBindings)..."
kubectl apply -f "${SCRIPT_DIR}/rbac.yaml" ${DRY_RUN}

# ── Step 5: Network Policies ──
echo "→ Applying Network Policies..."
kubectl apply -f "${SCRIPT_DIR}/networkpolicy.yaml" ${DRY_RUN}

# ── Step 6: Stateful services (Postgres, Redis) ──
echo "→ Deploying PostgreSQL..."
kubectl apply -f "${SCRIPT_DIR}/postgres.yaml" ${DRY_RUN}

echo "→ Deploying Redis..."
kubectl apply -f "${SCRIPT_DIR}/redis.yaml" ${DRY_RUN}

echo "→ Waiting for PostgreSQL to be ready..."
if [ -z "${DRY_RUN}" ]; then
  kubectl rollout status statefulset/postgres -n "${NAMESPACE}" --timeout=120s
fi

echo "→ Waiting for Redis to be ready..."
if [ -z "${DRY_RUN}" ]; then
  kubectl rollout status deployment/redis -n "${NAMESPACE}" --timeout=60s
fi

# ── Step 7: Application services ──
echo "→ Deploying Backend..."
kubectl apply -f "${SCRIPT_DIR}/backend.yaml" ${DRY_RUN}

echo "→ Deploying Frontend..."
kubectl apply -f "${SCRIPT_DIR}/frontend.yaml" ${DRY_RUN}

echo "→ Deploying n8n..."
kubectl apply -f "${SCRIPT_DIR}/n8n.yaml" ${DRY_RUN}

# ── Step 8: Autoscaling & Disruption Budgets ──
echo "→ Applying HorizontalPodAutoscalers..."
kubectl apply -f "${SCRIPT_DIR}/hpa.yaml" ${DRY_RUN}

echo "→ Applying PodDisruptionBudgets..."
kubectl apply -f "${SCRIPT_DIR}/pdb.yaml" ${DRY_RUN}

# ── Step 9: Ingress ──
echo "→ Applying Ingress..."
kubectl apply -f "${SCRIPT_DIR}/ingress.yaml" ${DRY_RUN}

# ── Step 10: Backup CronJob ──
echo "→ Applying PostgreSQL backup CronJob..."
kubectl apply -f "${SCRIPT_DIR}/backup-cronjob.yaml" ${DRY_RUN}

# ── Step 11: Wait for rollouts ──
if [ -z "${DRY_RUN}" ]; then
  echo ""
  echo "→ Waiting for deployments to be ready..."
  kubectl rollout status deployment/backend -n "${NAMESPACE}" --timeout=180s
  kubectl rollout status deployment/frontend -n "${NAMESPACE}" --timeout=120s
  kubectl rollout status deployment/n8n -n "${NAMESPACE}" --timeout=120s

  echo ""
  echo "╔══════════════════════════════════════════════════════════╗"
  echo "║  Deployment complete!                                   ║"
  echo "╚══════════════════════════════════════════════════════════╝"
  echo ""
  echo "  Pods:"
  kubectl get pods -n "${NAMESPACE}" -o wide
  echo ""
  echo "  Services:"
  kubectl get svc -n "${NAMESPACE}"
  echo ""
  echo "  Ingress:"
  kubectl get ingress -n "${NAMESPACE}"
else
  echo ""
  echo "Dry run complete — no changes applied."
fi
