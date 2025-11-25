#!/usr/bin/env bash
# Configure UFW firewall for SSH protection
# NOTE: HTTP/HTTPS traffic now uses Cloudflare Tunnel (no published ports)
# This script configures UFW for SSH protection only

set -euo pipefail

# Source common functions and Azure config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"
# shellcheck source=../azure-config.sh
source "$SCRIPT_DIR/../azure-config.sh"

require_root

echo "=== UFW Firewall Configuration ==="
echo ""

print_info "Architecture:"
print_info "  - HTTP/HTTPS ingress via Cloudflare Tunnel (no published ports)"
print_info "  - SSH access via traditional networking (UFW protected)"
print_info "  - See docs/adr/01-infrastructure.md for details"
echo ""

# Check if UFW is installed
if ! command_exists ufw; then
    print_error "UFW is not installed"
    print_info "Run deploy/setup/06-install-ufw.sh first"
    exit 1
fi
print_status "UFW found"

echo ""

# Configure UFW policies and SSH
print_info "Configuring UFW for SSH protection..."

# Set default policies
ufw default deny incoming
ufw default allow outgoing

# Allow SSH (port 22)
ufw allow 22/tcp

# Enable UFW
ufw --force enable

print_status "UFW configured for SSH protection"

# Show UFW status
echo ""
print_info "Current UFW status:"
ufw status verbose

echo ""
print_info "Note: Cloudflare IP whitelisting for HTTP/HTTPS is NOT needed"
print_info "Traffic flows: Internet → Cloudflare Edge → Encrypted Tunnel → Application"
print_info "No inbound ports 80/443 on VM (eliminates Docker/UFW firewall bypass)"
echo ""
print_status "UFW configuration complete"
