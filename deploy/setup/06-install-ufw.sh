#!/usr/bin/env bash
# Install UFW firewall (configuration happens later with ufw_cloudflare.py)

set -euo pipefail

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"
# shellcheck source=../azure-config.sh
source "$SCRIPT_DIR/../azure-config.sh"

require_root

echo "=== UFW Installation ==="
echo ""

# Check if UFW is already installed
if command_exists ufw; then
    print_warning "UFW is already installed"
    ufw version
else
    # Install UFW
    print_info "Installing UFW..."
    apt-get install -y ufw
    print_status "UFW installed"
fi

print_warning "UFW is NOT yet enabled - will be configured with Cloudflare IPs using ufw_cloudflare.py"

echo ""
print_info "After deployment, run:"
print_info "  sudo python3 $APP_DIR/docker/scripts/ufw_cloudflare.py"
echo ""
print_status "UFW installation complete"
