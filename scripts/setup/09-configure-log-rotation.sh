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

# Check if daemon.json exists
if [ -f "$DOCKER_DAEMON_JSON" ]; then
    print_warning "Docker daemon.json already exists"
    cat "$DOCKER_DAEMON_JSON"
    echo ""
    read -p "Overwrite with log rotation config? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
        print_info "Skipping log rotation configuration"
        exit 0
    fi
fi

# Create daemon.json with log rotation
print_info "Configuring Docker log rotation (max 10MB, 3 files)..."
cat > "$DOCKER_DAEMON_JSON" <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

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
