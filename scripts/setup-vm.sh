#!/usr/bin/env bash
# Setup Azure VM with Docker, security hardening, and deployment tooling
# This is a STUB script - full implementation will be in Issue #241

set -euo pipefail

# Source Azure configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./azure-config.sh
source "$SCRIPT_DIR/azure-config.sh"

echo "=== Azure VM Setup (STUB - Issue #241) ==="
echo ""
echo "This script will configure the VM for production deployment:"
echo "  - Target VM: $AZURE_VM_NAME"
echo "  - Admin User: $AZURE_ADMIN_USERNAME"
echo "  - Deploy User: $DEPLOYMENT_USER"
echo "  - App Directory: $APP_DIR"
echo ""
echo "Full implementation tasks (Issue #241):"
echo "  1. Update system packages (apt update && apt upgrade)"
echo "  2. Install Docker Engine (latest stable)"
echo "  3. Install Docker Compose v2"
echo "  4. Install Azure CLI"
echo "  5. Configure fail2ban"
echo "     - SSH jail (5 attempts, 10min ban)"
echo "     - HTTP jail for rate limiting"
echo "  6. Harden SSH configuration"
echo "     - Disable password authentication"
echo "     - Disable root login"
echo "     - Use key-only authentication"
echo "  7. Install and configure UFW firewall"
echo "     - Default deny incoming"
echo "     - Allow SSH (port 22)"
echo "     - Cloudflare IPs only for 80/443 (via ufw-cloudflare.sh)"
echo "  8. Create deployment user"
echo "     - Add to docker group"
echo "     - Configure SSH keys"
echo "     - Set up application directory"
echo "  9. Configure log rotation"
echo " 10. Set timezone to UTC"
echo ""
echo "Security features:"
echo "  - fail2ban: Automated IP banning"
echo "  - UFW: Firewall with Cloudflare IP whitelisting"
echo "  - SSH: Key-only, no passwords, no root"
echo "  - Docker: Rootless mode for deployment user"
echo ""
echo "NOTE: This is a stub. Actual setup will be implemented in Issue #241."
