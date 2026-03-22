#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════
# AWS Staging — One-Command Deploy
#
# Usage:
#   ./deploy.sh up        # Provision infra + deploy app
#   ./deploy.sh push      # Push code to existing VM
#   ./deploy.sh status    # Show staging URLs and status
#   ./deploy.sh ssh       # SSH into the staging VM
#   ./deploy.sh logs      # Tail docker logs on staging
#   ./deploy.sh destroy   # Tear down everything
# ═══════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[AWS-STAGING]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

get_ip() {
  cd "$SCRIPT_DIR"
  terraform output -raw app_public_ip 2>/dev/null || echo ""
}

get_key() {
  cd "$SCRIPT_DIR"
  terraform output -raw ssh_command 2>/dev/null | grep -oP '~/.ssh/\K[^ ]+\.pem' || echo ""
}

cmd_up() {
  log "Provisioning AWS staging infrastructure..."

  cd "$SCRIPT_DIR"

  if [ ! -f terraform.tfvars ]; then
    err "Missing terraform.tfvars. Run:"
    echo "  cp terraform.tfvars.example terraform.tfvars"
    echo "  # Edit terraform.tfvars with your SSH key name"
    exit 1
  fi

  # Create SSH key if needed
  KEY_NAME=$(grep ec2_key_name terraform.tfvars | cut -d'"' -f2)
  if [ -n "$KEY_NAME" ] && [ ! -f ~/.ssh/${KEY_NAME}.pem ]; then
    log "Creating SSH key pair: $KEY_NAME"
    aws ec2 create-key-pair --key-name "$KEY_NAME" \
      --query 'KeyMaterial' --output text > ~/.ssh/${KEY_NAME}.pem
    chmod 600 ~/.ssh/${KEY_NAME}.pem
  fi

  terraform init -upgrade
  terraform plan -out=tfplan
  terraform apply tfplan
  rm -f tfplan

  IP=$(get_ip)
  log "Infrastructure ready. Waiting 60s for EC2 to initialize..."
  sleep 60

  # Push code
  cmd_push

  echo ""
  log "=========================================="
  log " AWS Staging Deployed!"
  log "=========================================="
  terraform output
}

cmd_push() {
  IP=$(get_ip)
  KEY=$(get_key)

  if [ -z "$IP" ]; then
    err "No staging VM found. Run: ./deploy.sh up"
    exit 1
  fi

  SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
  if [ -n "$KEY" ]; then
    SSH_OPTS="$SSH_OPTS -i ~/.ssh/$KEY"
  fi

  log "Syncing project to $IP..."
  rsync -az -e "ssh $SSH_OPTS" \
    --exclude='.next' --exclude='node_modules' --exclude='__pycache__' \
    --exclude='.git' --exclude='*.db' --exclude='.env' --exclude='pgdata' \
    --exclude='venv' --exclude='.venv' --exclude='infra/staging' \
    "$PROJECT_ROOT/" "ubuntu@${IP}:~/llm-platform/"

  log "Building and starting containers..."
  ssh $SSH_OPTS "ubuntu@${IP}" \
    "cd ~/llm-platform && docker compose -f docker-compose.staging-aws.yml up -d --build"

  log "Deployment complete!"
  echo -e " Frontend: ${CYAN}http://${IP}:3000${NC}"
  echo -e " Backend:  ${CYAN}http://${IP}:8000/docs${NC}"
  echo -e " n8n:      ${CYAN}http://${IP}:5678${NC}"
}

cmd_status() {
  IP=$(get_ip)
  if [ -z "$IP" ]; then
    err "No staging VM found."
    exit 1
  fi

  echo ""
  cd "$SCRIPT_DIR" && terraform output
  echo ""
  log "Checking container health..."

  SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
  KEY=$(get_key)
  [ -n "$KEY" ] && SSH_OPTS="$SSH_OPTS -i ~/.ssh/$KEY"

  ssh $SSH_OPTS "ubuntu@${IP}" "cd ~/llm-platform && docker compose -f docker-compose.staging-aws.yml ps" 2>/dev/null || warn "Could not reach VM"
}

cmd_ssh() {
  IP=$(get_ip)
  KEY=$(get_key)
  if [ -z "$IP" ]; then
    err "No staging VM found."
    exit 1
  fi

  SSH_CMD="ssh -o StrictHostKeyChecking=no"
  [ -n "$KEY" ] && SSH_CMD="$SSH_CMD -i ~/.ssh/$KEY"
  SSH_CMD="$SSH_CMD ubuntu@${IP}"

  log "Connecting to $IP..."
  exec $SSH_CMD
}

cmd_logs() {
  IP=$(get_ip)
  KEY=$(get_key)
  if [ -z "$IP" ]; then
    err "No staging VM found."
    exit 1
  fi

  SSH_OPTS="-o StrictHostKeyChecking=no"
  [ -n "$KEY" ] && SSH_OPTS="$SSH_OPTS -i ~/.ssh/$KEY"

  ssh $SSH_OPTS "ubuntu@${IP}" \
    "cd ~/llm-platform && docker compose -f docker-compose.staging-aws.yml logs --tail=50 -f"
}

cmd_destroy() {
  warn "This will destroy ALL staging infrastructure (VM, RDS, ElastiCache, secrets)."
  read -p "Type 'destroy' to confirm: " confirm
  if [ "$confirm" != "destroy" ]; then
    log "Cancelled."
    exit 0
  fi

  cd "$SCRIPT_DIR"
  terraform destroy -auto-approve
  log "Staging infrastructure destroyed. No more charges."
}

# ── Main ──
case "${1:-}" in
  up)      cmd_up ;;
  push)    cmd_push ;;
  status)  cmd_status ;;
  ssh)     cmd_ssh ;;
  logs)    cmd_logs ;;
  destroy) cmd_destroy ;;
  *)
    echo ""
    echo "AWS Staging Deployment"
    echo ""
    echo "Usage:"
    echo "  ./deploy.sh up        Provision RDS + ElastiCache + EC2 and deploy app"
    echo "  ./deploy.sh push      Push code changes to existing staging VM"
    echo "  ./deploy.sh status    Show URLs, endpoints, and container health"
    echo "  ./deploy.sh ssh       SSH into the staging VM"
    echo "  ./deploy.sh logs      Tail container logs"
    echo "  ./deploy.sh destroy   Tear down everything (stops billing)"
    echo ""
    echo "Estimated cost: ~\$50/mo"
    echo "  EC2 t3.medium      ~\$30/mo"
    echo "  RDS db.t3.micro    ~\$13/mo"
    echo "  ElastiCache t3.micro ~\$12/mo"
    echo ""
    ;;
esac
