#!/usr/bin/env bash
# Configure UFW firewall with Cloudflare IP whitelisting

set -euo pipefail

# Source common functions and Azure config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"
# shellcheck source=../azure-config.sh
source "$SCRIPT_DIR/../azure-config.sh"

require_root

echo "=== UFW Cloudflare Configuration ==="
echo ""

# Check prerequisites
print_info "Checking prerequisites..."

# Check if Python 3 is available
if ! command_exists python3; then
    print_error "Python 3 is not installed"
    exit 1
fi
print_status "Python 3 found"

# Check if httpx is available
if ! python3 -c "import httpx" 2>/dev/null; then
    print_warning "python3-httpx not found, installing..."
    apt-get update
    apt-get install -y python3-httpx
    print_status "python3-httpx installed"
else
    print_status "python3-httpx already installed"
fi

# Check if UFW is installed
if ! command_exists ufw; then
    print_error "UFW is not installed"
    print_info "Run deploy/setup/06-install-ufw.sh first"
    exit 1
fi
print_status "UFW found"

# Check if ufw_cloudflare.py exists
UFW_SCRIPT="$APP_DIR/docker/scripts/ufw_cloudflare.py"
if [ ! -f "$UFW_SCRIPT" ]; then
    print_error "UFW Cloudflare script not found: $UFW_SCRIPT"
    print_info "Make sure application files are deployed to $APP_DIR"
    exit 1
fi
print_status "UFW script found"

echo ""

# Run UFW configuration script
print_info "Running UFW Cloudflare configuration..."
python3 "$UFW_SCRIPT"

print_status "UFW configured with Cloudflare IPs"

# Show UFW status
echo ""
print_info "Current UFW status:"
ufw status verbose

echo ""
print_status "UFW Cloudflare configuration complete"
