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
DEBIAN_FRONTEND=noninteractive apt-get update

# Upgrade packages
print_info "Upgrading packages (this may take a few minutes)..."
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

print_status "System packages updated"

# Install common dependencies
print_info "Installing common dependencies..."
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    jq \
    build-essential \
    libssl-dev \
    libffi-dev

print_status "Common dependencies installed"
print_info "  - jq: JSON processor for azure-config.sh"
print_info "  - build-essential: C compiler for Python packages (asyncpg, hiredis, cryptography)"
print_info "  - libssl-dev: OpenSSL headers for cryptography package"
print_info "  - libffi-dev: FFI headers for cryptography package"

# Set timezone
print_info "Setting timezone to UTC..."
if timedatectl set-timezone UTC; then
    print_status "Timezone set to UTC"
else
    print_warning "Failed to set timezone (non-critical)"
fi

echo ""
print_status "System update complete"
