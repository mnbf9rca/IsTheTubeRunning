#!/usr/bin/env bash
# Configure Docker log rotation

set -euo pipefail

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"

require_root

echo "=== Docker Log Rotation ==="
echo ""

DOCKER_DAEMON_JSON="/etc/docker/daemon.json"

# Define log rotation config to merge
LOG_ROTATION_CONFIG='{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}'

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    print_error "jq is required but not installed"
    print_error "This should have been installed in 01-system-update.sh"
    exit 1
fi

# Merge or create daemon.json with log rotation
print_info "Configuring Docker log rotation (max 10MB, 3 files)..."
if [ -f "$DOCKER_DAEMON_JSON" ]; then
    print_info "Existing daemon.json found - merging log rotation settings..."
    # Backup existing file
    cp "$DOCKER_DAEMON_JSON" "${DOCKER_DAEMON_JSON}.backup"
    print_status "Backup created: ${DOCKER_DAEMON_JSON}.backup"

    # Merge log rotation settings into existing config
    MERGED_CONFIG=$(jq -s '.[0] * .[1]' "$DOCKER_DAEMON_JSON" <(echo "$LOG_ROTATION_CONFIG"))
    echo "$MERGED_CONFIG" | jq '.' > "$DOCKER_DAEMON_JSON"
    print_status "Log rotation settings merged with existing config"
else
    print_info "Creating new daemon.json with log rotation..."
    echo "$LOG_ROTATION_CONFIG" | jq '.' > "$DOCKER_DAEMON_JSON"
    print_status "New daemon.json created"
fi

print_status "Log rotation configured"

# Restart Docker to apply changes
print_info "Restarting Docker service..."
systemctl restart docker

# Verify Docker is running
if systemctl is-active --quiet docker; then
    print_status "Docker restarted successfully"
else
    print_error "Docker failed to restart"
    exit 1
fi

echo ""
print_status "Docker log rotation complete"
