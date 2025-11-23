#!/usr/bin/env bash
# Post-deployment health check script for IsTheTubeRunning
# Verifies all services are running and healthy
#
# Usage:
#   ./health-check.sh
#
# Exit codes:
#   0 - All checks passed
#   1 - One or more checks failed

set -euo pipefail

FAILED=0

echo "=== IsTheTubeRunning Health Check ==="
echo "Timestamp: $(date)"
echo ""

# Check 1: Docker containers running
echo "[1/5] Checking Docker containers..."
EXPECTED_CONTAINERS=("isthetube-postgres-prod" "isthetube-redis-prod" "isthetube-backend-prod" "isthetube-celery-worker-prod" "isthetube-celery-beat-prod" "isthetube-frontend-prod")
RUNNING_COUNT=0

for container in "${EXPECTED_CONTAINERS[@]}"; do
    if docker ps --filter "name=$container" --filter "status=running" --format '{{.Names}}' | grep -q "$container"; then
        echo "  ✓ $container is running"
        ((RUNNING_COUNT++))
    else
        echo "  ✗ $container is NOT running"
        FAILED=1
    fi
done

echo "  Summary: $RUNNING_COUNT/${#EXPECTED_CONTAINERS[@]} containers running"
echo ""

# Check 2: Container health status
echo "[2/5] Checking container health status..."
for container in isthetube-postgres-prod isthetube-redis-prod isthetube-backend-prod; do
    HEALTH=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no healthcheck{{end}}' "$container" 2>/dev/null || echo "not found")

    if [[ "$HEALTH" == "healthy" ]]; then
        echo "  ✓ $container: $HEALTH"
    elif [[ "$HEALTH" == "no healthcheck" ]]; then
        echo "  ○ $container: $HEALTH (not configured)"
    else
        echo "  ✗ $container: $HEALTH"
        [[ "$HEALTH" != "no healthcheck" ]] && FAILED=1
    fi
done
echo ""

# Check 3: HTTP endpoints
echo "[3/5] Checking HTTP endpoints..."

# Health endpoint
if HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/health); then
    if [[ "$HTTP_STATUS" == "200" ]]; then
        echo "  ✓ /health returned $HTTP_STATUS"
    else
        echo "  ✗ /health returned $HTTP_STATUS (expected 200)"
        FAILED=1
    fi
else
    echo "  ✗ /health request failed"
    FAILED=1
fi

# Readiness endpoint
if HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ready); then
    if [[ "$HTTP_STATUS" == "200" ]]; then
        echo "  ✓ /ready returned $HTTP_STATUS"
    else
        echo "  ✗ /ready returned $HTTP_STATUS (expected 200)"
        FAILED=1
    fi
else
    echo "  ✗ /ready request failed"
    FAILED=1
fi

# Frontend root
if HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/); then
    if [[ "$HTTP_STATUS" == "200" ]]; then
        echo "  ✓ / (frontend) returned $HTTP_STATUS"
    else
        echo "  ✗ / (frontend) returned $HTTP_STATUS (expected 200)"
        FAILED=1
    fi
else
    echo "  ✗ / (frontend) request failed"
    FAILED=1
fi
echo ""

# Check 4: Container logs for errors
echo "[4/5] Checking container logs for recent errors..."
ERROR_COUNT=0
for container in isthetube-backend-prod isthetube-celery-worker-prod isthetube-celery-beat-prod; do
    # Check last 20 lines of logs for ERROR/CRITICAL/FATAL level messages
    if docker logs --tail 20 "$container" 2>&1 | grep -Ei "ERROR|CRITICAL|FATAL"; then
        ERROR_COUNT=$((ERROR_COUNT + 1))
        echo "  ⚠ $container has recent errors in logs"
    else
        echo "  ✓ $container has no recent errors"
    fi
done

if [[ $ERROR_COUNT -gt 0 ]]; then
    echo "  Note: $ERROR_COUNT container(s) have errors in logs (warning only)"
fi
echo ""

# Check 5: Disk space
echo "[5/5] Checking disk space..."
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [[ $DISK_USAGE -lt 80 ]]; then
    echo "  ✓ Disk usage: ${DISK_USAGE}% (< 80%)"
elif [[ $DISK_USAGE -lt 90 ]]; then
    echo "  ⚠ Disk usage: ${DISK_USAGE}% (warning: approaching 90%)"
else
    echo "  ✗ Disk usage: ${DISK_USAGE}% (critical: ≥ 90%)"
    FAILED=1
fi
echo ""

# Summary
echo "=== Health Check Summary ==="
if [[ $FAILED -eq 0 ]]; then
    echo "✓ All checks passed"
    exit 0
else
    echo "✗ Some checks failed - review output above"
    exit 1
fi
