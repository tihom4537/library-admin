#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Arivu Deploy Script
# Usage: ./deploy.sh <ec2-user>@<ec2-ip> [path-to-pem]
# Example: ./deploy.sh ubuntu@13.126.45.22 ~/.ssh/arivu.pem
# ─────────────────────────────────────────────────────────────
set -e

SSH_TARGET=${1:?Usage: ./deploy.sh user@host [pem-file]}
PEM=${2:-~/.ssh/id_rsa}
REMOTE_DIR=/opt/arivu
SSH="ssh -i $PEM -o StrictHostKeyChecking=no $SSH_TARGET"

echo "▶ Deploying Arivu to $SSH_TARGET"

# 1. Install Docker + Compose on the EC2 (idempotent)
$SSH << 'SETUP'
  if ! command -v docker &>/dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    newgrp docker
  fi
  if ! docker compose version &>/dev/null; then
    echo "Installing Docker Compose plugin..."
    sudo apt-get install -y docker-compose-plugin 2>/dev/null || \
    sudo yum install -y docker-compose-plugin 2>/dev/null || true
  fi
  echo "Docker: $(docker --version)"
  echo "Compose: $(docker compose version)"
SETUP

# 2. Sync project files (excludes node_modules, .venv, __pycache__, dist)
echo "▶ Syncing files..."
rsync -avz --progress \
  -e "ssh -i $PEM -o StrictHostKeyChecking=no" \
  --exclude 'node_modules' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'arivu-admin/dist' \
  --exclude '.git' \
  /Applications/whatomate/arivu-backend \
  /Applications/whatomate/arivu-admin \
  /Applications/whatomate/docker-compose.prod.yml \
  $SSH_TARGET:$REMOTE_DIR/

# 3. Build and start containers
echo "▶ Building and starting containers..."
$SSH << DEPLOY
  cd $REMOTE_DIR
  docker compose -f docker-compose.prod.yml pull redis 2>/dev/null || true
  docker compose -f docker-compose.prod.yml build --no-cache
  docker compose -f docker-compose.prod.yml up -d
  echo ""
  echo "✅ Running containers:"
  docker compose -f docker-compose.prod.yml ps
DEPLOY

echo ""
echo "✅ Done! Admin portal: http://$(echo $SSH_TARGET | cut -d@ -f2)"
echo "   Backend API:  http://$(echo $SSH_TARGET | cut -d@ -f2)/admin/docs"
