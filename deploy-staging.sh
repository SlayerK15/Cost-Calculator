#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# LLM Cloud Platform — Staging Deployment Script
#
# Deploys to a single cloud VM with Docker Compose.
# Supports: AWS, GCP, Azure (or any VM with SSH access)
#
# Usage:
#   ./deploy-staging.sh aws          # Create AWS EC2 + deploy
#   ./deploy-staging.sh gcp          # Create GCP VM + deploy
#   ./deploy-staging.sh azure        # Create Azure VM + deploy
#   ./deploy-staging.sh ssh user@ip  # Deploy to existing VM
#   ./deploy-staging.sh teardown aws # Destroy staging infra
# ═══════════════════════════════════════════════════════════════

STAGING_NAME="llm-platform-staging"
STAGING_REGION_AWS="us-east-1"
STAGING_REGION_GCP="us-central1-a"
STAGING_REGION_AZURE="eastus"
INSTANCE_TYPE_AWS="t3.medium"    # 2 vCPU, 4GB — ~$30/mo
INSTANCE_TYPE_GCP="e2-medium"    # 2 vCPU, 4GB — ~$25/mo
INSTANCE_TYPE_AZURE="Standard_B2s" # 2 vCPU, 4GB — ~$30/mo

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[STAGING]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Generate secure secrets ──
generate_secrets() {
    log "Generating staging secrets..."
    SECRET_KEY=$(openssl rand -hex 32)
    POSTGRES_PASSWORD=$(openssl rand -hex 16)
    N8N_PASSWORD=$(openssl rand -hex 12)
    N8N_CALLBACK_SECRET=$(openssl rand -hex 16)
    CREDENTIAL_KEY=$(openssl rand -hex 32)
}

# ── Create .env file for staging ──
write_env_file() {
    local public_ip="${1:-localhost}"
    cat > /tmp/llm-staging.env << ENVEOF
DEBUG=true
SECRET_KEY=${SECRET_KEY}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
N8N_PASSWORD=${N8N_PASSWORD}
N8N_CALLBACK_SECRET=${N8N_CALLBACK_SECRET}
CREDENTIAL_ENCRYPTION_KEY=${CREDENTIAL_KEY}
CORS_ORIGINS=http://${public_ip}:3000
AGENT_LLM_API_KEY=
AGENT_LLM_PROVIDER=openai
AGENT_LLM_MODEL=gpt-4o-mini
HF_TOKEN=
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRO_PRICE_ID=
STRIPE_ENTERPRISE_PRICE_ID=
N8N_USER=admin
ENVEOF
    log "Staging .env written (secrets auto-generated)"
}

# ── Setup script that runs on the VM ──
VM_SETUP_SCRIPT='#!/bin/bash
set -euo pipefail
echo "=== Installing Docker ==="
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    sudo systemctl enable docker
    sudo systemctl start docker
fi

if ! docker compose version &>/dev/null; then
    sudo apt-get update -qq && sudo apt-get install -y -qq docker-compose-plugin
fi

echo "=== Setting up app ==="
cd ~/llm-platform
cp .env.staging .env
docker compose up -d --build
echo ""
echo "=== Staging deployment complete ==="
docker compose ps
'

# ── Deploy to existing VM via SSH ──
deploy_ssh() {
    local ssh_target="$1"
    log "Deploying to ${ssh_target}..."

    generate_secrets
    local ip=$(echo "$ssh_target" | cut -d@ -f2)
    write_env_file "$ip"

    log "Syncing project files..."
    rsync -az --exclude='.next' --exclude='node_modules' --exclude='__pycache__' \
          --exclude='.git' --exclude='*.db' --exclude='.env' --exclude='pgdata' \
          --exclude='venv' --exclude='.venv' \
          ./ "${ssh_target}:~/llm-platform/"

    log "Uploading staging env..."
    scp /tmp/llm-staging.env "${ssh_target}:~/llm-platform/.env"
    rm -f /tmp/llm-staging.env

    log "Running setup on VM..."
    ssh "$ssh_target" "cd ~/llm-platform && bash -c '${VM_SETUP_SCRIPT}'"

    echo ""
    log "=========================================="
    log " Staging deployed successfully!"
    log "=========================================="
    echo -e " Frontend:  ${CYAN}http://${ip}:3000${NC}"
    echo -e " Backend:   ${CYAN}http://${ip}:8000/docs${NC}"
    echo -e " n8n:       ${CYAN}http://${ip}:5678${NC}"
    echo -e " n8n login: ${CYAN}admin / ${N8N_PASSWORD}${NC}"
    echo ""
    warn "This is a STAGING environment — do not use in production."
}

# ── AWS EC2 ──
deploy_aws() {
    log "Creating AWS EC2 instance for staging..."
    command -v aws >/dev/null || { err "AWS CLI not installed. Install: https://aws.amazon.com/cli/"; exit 1; }

    # Get latest Ubuntu 22.04 AMI
    AMI_ID=$(aws ec2 describe-images \
        --owners 099720109477 \
        --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
        --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
        --output text --region "$STAGING_REGION_AWS")

    # Create security group
    SG_ID=$(aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=${STAGING_NAME}-sg" \
        --query 'SecurityGroups[0].GroupId' --output text --region "$STAGING_REGION_AWS" 2>/dev/null || echo "None")

    if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
        SG_ID=$(aws ec2 create-security-group \
            --group-name "${STAGING_NAME}-sg" \
            --description "Staging LLM Platform" \
            --region "$STAGING_REGION_AWS" \
            --output text --query 'GroupId')

        for port in 22 3000 8000 5678; do
            aws ec2 authorize-security-group-ingress \
                --group-id "$SG_ID" \
                --protocol tcp --port "$port" --cidr 0.0.0.0/0 \
                --region "$STAGING_REGION_AWS" 2>/dev/null || true
        done
        log "Security group created: $SG_ID"
    fi

    # Create key pair if not exists
    KEY_NAME="${STAGING_NAME}-key"
    if ! aws ec2 describe-key-pairs --key-names "$KEY_NAME" --region "$STAGING_REGION_AWS" &>/dev/null; then
        aws ec2 create-key-pair --key-name "$KEY_NAME" \
            --query 'KeyMaterial' --output text \
            --region "$STAGING_REGION_AWS" > ~/.ssh/${KEY_NAME}.pem
        chmod 600 ~/.ssh/${KEY_NAME}.pem
        log "SSH key created: ~/.ssh/${KEY_NAME}.pem"
    fi

    # Launch instance
    INSTANCE_ID=$(aws ec2 run-instances \
        --image-id "$AMI_ID" \
        --instance-type "$INSTANCE_TYPE_AWS" \
        --key-name "$KEY_NAME" \
        --security-group-ids "$SG_ID" \
        --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":30,"VolumeType":"gp3"}}]' \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${STAGING_NAME}}]" \
        --region "$STAGING_REGION_AWS" \
        --query 'Instances[0].InstanceId' --output text)

    log "Instance launched: $INSTANCE_ID — waiting for public IP..."
    aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$STAGING_REGION_AWS"

    PUBLIC_IP=$(aws ec2 describe-instances \
        --instance-ids "$INSTANCE_ID" \
        --query 'Reservations[0].Instances[0].PublicIpAddress' --output text \
        --region "$STAGING_REGION_AWS")

    log "VM ready at $PUBLIC_IP — waiting for SSH..."
    sleep 30  # Wait for SSH to come up

    deploy_ssh "ubuntu@${PUBLIC_IP}"

    echo ""
    echo -e " To SSH:    ${CYAN}ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@${PUBLIC_IP}${NC}"
    echo -e " To teardown: ${CYAN}./deploy-staging.sh teardown aws${NC}"
}

# ── GCP ──
deploy_gcp() {
    log "Creating GCP VM for staging..."
    command -v gcloud >/dev/null || { err "gcloud CLI not installed. Install: https://cloud.google.com/sdk/docs/install"; exit 1; }

    gcloud compute instances create "$STAGING_NAME" \
        --zone="$STAGING_REGION_GCP" \
        --machine-type="$INSTANCE_TYPE_GCP" \
        --image-family=ubuntu-2204-lts \
        --image-project=ubuntu-os-cloud \
        --boot-disk-size=30GB \
        --boot-disk-type=pd-balanced \
        --tags=staging-llm \
        --metadata=startup-script="#!/bin/bash
apt-get update -qq
apt-get install -y -qq rsync" \
        2>/dev/null

    # Open firewall
    gcloud compute firewall-rules create "${STAGING_NAME}-allow" \
        --allow=tcp:3000,tcp:8000,tcp:5678 \
        --target-tags=staging-llm \
        --description="Staging LLM Platform ports" 2>/dev/null || true

    PUBLIC_IP=$(gcloud compute instances describe "$STAGING_NAME" \
        --zone="$STAGING_REGION_GCP" \
        --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

    log "VM ready at $PUBLIC_IP — waiting for SSH..."
    sleep 30

    deploy_ssh "$(whoami)@${PUBLIC_IP}"

    echo ""
    echo -e " To SSH:    ${CYAN}gcloud compute ssh ${STAGING_NAME} --zone=${STAGING_REGION_GCP}${NC}"
    echo -e " To teardown: ${CYAN}./deploy-staging.sh teardown gcp${NC}"
}

# ── Azure ──
deploy_azure() {
    log "Creating Azure VM for staging..."
    command -v az >/dev/null || { err "Azure CLI not installed. Install: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli"; exit 1; }

    # Create resource group
    az group create --name "${STAGING_NAME}-rg" --location "$STAGING_REGION_AZURE" --output none

    # Create VM
    az vm create \
        --resource-group "${STAGING_NAME}-rg" \
        --name "$STAGING_NAME" \
        --image Ubuntu2204 \
        --size "$INSTANCE_TYPE_AZURE" \
        --admin-username azureuser \
        --generate-ssh-keys \
        --os-disk-size-gb 30 \
        --output none

    # Open ports
    az vm open-port --resource-group "${STAGING_NAME}-rg" --name "$STAGING_NAME" \
        --port 3000,8000,5678 --priority 1000 --output none

    PUBLIC_IP=$(az vm show --resource-group "${STAGING_NAME}-rg" --name "$STAGING_NAME" \
        --show-details --query publicIps --output tsv)

    log "VM ready at $PUBLIC_IP — waiting for SSH..."
    sleep 30

    deploy_ssh "azureuser@${PUBLIC_IP}"

    echo ""
    echo -e " To SSH:    ${CYAN}ssh azureuser@${PUBLIC_IP}${NC}"
    echo -e " To teardown: ${CYAN}./deploy-staging.sh teardown azure${NC}"
}

# ── Teardown ──
teardown() {
    local provider="${1:-}"
    case "$provider" in
        aws)
            log "Tearing down AWS staging..."
            INSTANCE_ID=$(aws ec2 describe-instances \
                --filters "Name=tag:Name,Values=${STAGING_NAME}" "Name=instance-state-name,Values=running" \
                --query 'Reservations[0].Instances[0].InstanceId' --output text \
                --region "$STAGING_REGION_AWS")
            if [ "$INSTANCE_ID" != "None" ] && [ -n "$INSTANCE_ID" ]; then
                aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --region "$STAGING_REGION_AWS" --output none
                log "Instance $INSTANCE_ID terminated"
            fi
            aws ec2 delete-security-group --group-name "${STAGING_NAME}-sg" --region "$STAGING_REGION_AWS" 2>/dev/null || true
            aws ec2 delete-key-pair --key-name "${STAGING_NAME}-key" --region "$STAGING_REGION_AWS" 2>/dev/null || true
            rm -f ~/.ssh/${STAGING_NAME}-key.pem
            log "AWS staging torn down"
            ;;
        gcp)
            log "Tearing down GCP staging..."
            gcloud compute instances delete "$STAGING_NAME" --zone="$STAGING_REGION_GCP" --quiet 2>/dev/null || true
            gcloud compute firewall-rules delete "${STAGING_NAME}-allow" --quiet 2>/dev/null || true
            log "GCP staging torn down"
            ;;
        azure)
            log "Tearing down Azure staging..."
            az group delete --name "${STAGING_NAME}-rg" --yes --no-wait
            log "Azure staging torn down (resource group deletion in progress)"
            ;;
        *)
            err "Usage: ./deploy-staging.sh teardown <aws|gcp|azure>"
            exit 1
            ;;
    esac
}

# ── Main ──
case "${1:-}" in
    aws)
        deploy_aws
        ;;
    gcp)
        deploy_gcp
        ;;
    azure)
        deploy_azure
        ;;
    ssh)
        [ -z "${2:-}" ] && { err "Usage: ./deploy-staging.sh ssh user@ip"; exit 1; }
        deploy_ssh "$2"
        ;;
    teardown)
        teardown "${2:-}"
        ;;
    *)
        echo ""
        echo "LLM Cloud Platform — Staging Deployment"
        echo ""
        echo "Usage:"
        echo "  ./deploy-staging.sh aws            Create EC2 instance + deploy (~\$30/mo)"
        echo "  ./deploy-staging.sh gcp            Create GCP VM + deploy (~\$25/mo)"
        echo "  ./deploy-staging.sh azure          Create Azure VM + deploy (~\$30/mo)"
        echo "  ./deploy-staging.sh ssh user@ip    Deploy to any existing VM"
        echo "  ./deploy-staging.sh teardown aws   Destroy AWS staging infra"
        echo "  ./deploy-staging.sh teardown gcp   Destroy GCP staging infra"
        echo "  ./deploy-staging.sh teardown azure Destroy Azure staging infra"
        echo ""
        ;;
esac
