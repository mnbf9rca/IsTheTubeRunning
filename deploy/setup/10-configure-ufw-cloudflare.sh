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
    print_error "python3-httpx not found"
    print_error "This should have been installed by 01-system-update.sh"
    print_error "Re-run setup-vm.sh or install manually: apt-get install -y python3-httpx"
    exit 1
fi
print_status "python3-httpx is installed"

# Check if UFW is installed
if ! command_exists ufw; then
    print_error "UFW is not installed"
    print_info "Run deploy/setup/06-install-ufw.sh first"
    exit 1
fi
print_status "UFW found"

# Check if ufw_cloudflare.py exists (in deploy directory)
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
UFW_SCRIPT="$DEPLOY_DIR/scripts/ufw_cloudflare.py"
if [ ! -f "$UFW_SCRIPT" ]; then
    print_error "UFW Cloudflare script not found: $UFW_SCRIPT"
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
