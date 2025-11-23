#!/usr/bin/env bash
# Update system packages and set timezone

set -euo pipefail

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"

require_root

echo "=== System Update ==="
echo ""

# Update package lists
print_info "Updating package lists..."
apt-get update

# Upgrade packages
print_info "Upgrading packages (this may take a few minutes)..."
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

print_status "System packages updated"

# Set timezone
print_info "Setting timezone to UTC..."
if timedatectl set-timezone UTC; then
    print_status "Timezone set to UTC"
else
    print_warning "Failed to set timezone (non-critical)"
fi

echo ""
print_status "System update complete"
