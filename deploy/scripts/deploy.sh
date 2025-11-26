#!/usr/bin/env bash
# Deployment script for IsTheTubeRunning
# Called by GitHub Actions via SSH
#
# This script:
# 1. Pulls latest code from release branch
# 2. Pulls new Docker images from GHCR
# 3. Restarts services with docker compose
# 4. Verifies deployment with health check
#
# Prerequisites:
# - deployuser must be in docker group (already configured)
# - /opt/isthetube directory with git repository
# - .env.secrets configured with DOTENV_KEY, CLOUDFLARE_TUNNEL_TOKEN, etc.

set -euo pipefail

APP_DIR="/opt/isthetube"
COMPOSE_FILE="$APP_DIR/deploy/docker-compose.prod.yml"

echo "=== IsTheTubeRunning Deployment Started ==="
echo "Timestamp: $(date -Iseconds)"
echo "User: $(whoami)"
echo ""

# Step 1: Pull latest code from release branch
echo "[1/4] Pulling latest code from release branch..."
cd "$APP_DIR"
git fetch origin release
git reset --hard origin/release
DEPLOYED_COMMIT=$(git rev-parse --short HEAD)
echo "✓ Code updated to commit: $DEPLOYED_COMMIT"
echo ""

# Step 2: Pull new images from GHCR
echo "[2/4] Pulling latest Docker images from GHCR..."
cd "$APP_DIR/deploy"
docker compose -f "$COMPOSE_FILE" pull
echo "✓ Images pulled successfully"
echo ""

# Step 3: Restart services with new images
echo "[3/4] Restarting services with docker compose..."
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans
echo "✓ Services restarted"
echo ""

# Step 4: Wait and verify deployment
echo "[4/4] Waiting for services to become healthy..."
sleep 45

# Check backend health endpoint
if curl -sf http://localhost/health > /dev/null; then
    echo "✓ Backend health check passed"
    echo ""
    echo "=== Deployment Complete ==="
    echo "Deployed commit: $DEPLOYED_COMMIT"
    echo "Timestamp: $(date -Iseconds)"
    exit 0
else
    echo "✗ ERROR: Backend health check failed"
    echo ""
    echo "Service status:"
    docker compose -f "$COMPOSE_FILE" ps
    echo ""
    echo "Recent logs:"
    docker compose -f "$COMPOSE_FILE" logs --tail=50
    exit 1
fi
