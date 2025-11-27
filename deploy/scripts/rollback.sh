#!/usr/bin/env bash
# Rollback script for IsTheTubeRunning
# Rolls back to a previous git commit and restarts services
#
# Usage:
#   ./rollback.sh [commit-sha]
#
# If no commit-sha provided, rolls back to HEAD~1 (previous commit)
#
# Prerequisites:
# - deployuser must be in docker group (already configured)
# - /opt/isthetube directory with git repository
# - .env.secrets configured

set -euo pipefail

APP_DIR="/opt/isthetube"
COMPOSE_FILE="$APP_DIR/deploy/docker-compose.prod.yml"

# Determine target commit (default to previous commit if not specified)
if [ $# -eq 1 ]; then
    TARGET_SHA="$1"
else
    TARGET_SHA=$(git -C "$APP_DIR" rev-parse HEAD~1)
fi

echo "=== IsTheTubeRunning Rollback Started ==="
echo "Timestamp: $(date -Iseconds)"
echo "Target commit: $TARGET_SHA"
echo ""

# Validate TARGET_SHA to prevent command injection
# Allow: commit SHAs (7-40 hex chars), HEAD~N notation, branch names
if ! echo "$TARGET_SHA" | grep -qE '^([a-f0-9]{7,40}|HEAD~[0-9]+|[a-zA-Z0-9/_-]+)$'; then
    echo "✗ ERROR: Invalid target SHA format: $TARGET_SHA"
    echo "Valid formats:"
    echo "  - Commit SHA: abc1234 or abc1234567890abcdef1234567890abcdef1234"
    echo "  - Relative: HEAD~1, HEAD~2, etc."
    echo "  - Branch: main, release, feature/branch-name"
    exit 1
fi

# Step 1: Checkout target commit
echo "[1/3] Checking out target commit..."
cd "$APP_DIR"
git fetch origin
git checkout "$TARGET_SHA"
ROLLED_BACK_COMMIT=$(git rev-parse --short HEAD)
echo "✓ Checked out commit: $ROLLED_BACK_COMMIT"
echo ""

# Step 2: Restart services (pulls images if tagged version exists)
echo "[2/3] Restarting services..."
cd "$APP_DIR/deploy"
# Pull attempt (may fail if commit-specific tag doesn't exist - that's OK)
docker compose -f "$COMPOSE_FILE" pull || echo "Note: Using existing images (no commit-specific tag found)"
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans --force-recreate
echo "✓ Services restarted"
echo ""

# Step 3: Wait and verify
echo "[3/3] Waiting for services to become healthy..."
sleep 45

# Check backend health endpoint
if curl -sf http://localhost/health > /dev/null; then
    echo "✓ Backend health check passed"
    echo ""
    echo "=== Rollback Complete ==="
    echo "Running version: $ROLLED_BACK_COMMIT"
    echo "Timestamp: $(date -Iseconds)"
    exit 0
else
    echo "✗ ERROR: Rollback health check failed"
    echo ""
    echo "Service status:"
    docker compose -f "$COMPOSE_FILE" ps
    echo ""
    echo "Recent logs:"
    docker compose -f "$COMPOSE_FILE" logs --tail=50
    exit 1
fi
