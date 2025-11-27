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
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans --force-recreate
echo "✓ Services restarted"
echo ""

# Step 4: Wait for backend to become healthy (with retry)
echo "[4/4] Waiting for backend to become healthy..."
MAX_ATTEMPTS=6
SLEEP_INTERVAL=15

for attempt in $(seq 1 $MAX_ATTEMPTS); do
    echo "Attempt $attempt/$MAX_ATTEMPTS: Checking backend health..."

    # Check if backend container is healthy using Docker's health check
    BACKEND_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' isthetube-backend-prod 2>/dev/null || echo "unknown")

    if [ "$BACKEND_HEALTH" = "healthy" ]; then
        echo "✓ Backend is healthy"
        echo ""
        echo "=== Deployment Complete ==="
        echo "Deployed commit: $DEPLOYED_COMMIT"
        echo "Timestamp: $(date -Iseconds)"
        exit 0
    fi

    if [ "$attempt" -lt "$MAX_ATTEMPTS" ]; then
        echo "Backend not healthy yet (status: $BACKEND_HEALTH), waiting ${SLEEP_INTERVAL}s..."
        sleep $SLEEP_INTERVAL
    fi
done

# All attempts failed
echo "✗ ERROR: Backend failed to become healthy after $((MAX_ATTEMPTS * SLEEP_INTERVAL)) seconds"
echo ""
echo "Service status:"
docker compose -f "$COMPOSE_FILE" ps
echo ""
echo "Recent logs:"
docker compose -f "$COMPOSE_FILE" logs --tail=50
exit 1
