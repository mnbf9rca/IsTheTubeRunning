#!/usr/bin/env bash
# Setup Azure VM with Docker, security hardening, and deployment tooling
# Orchestrates modular setup subscripts

set -euo pipefail

# Source Azure configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./azure-config.sh
source "$SCRIPT_DIR/azure-config.sh"
# shellcheck source=./setup/common.sh
source "$SCRIPT_DIR/setup/common.sh"

require_root

echo "========================================="
echo "  IsTheTubeRunning - VM Setup"
echo "========================================="
echo ""
echo "Checking prerequisites..."
echo ""

# Check internet connectivity
if ! ping -c 1 8.8.8.8 &> /dev/null; then
    print_error "No internet connectivity"
    exit 1
fi
print_status "Internet connectivity OK"

# Check if running on Ubuntu
if [ ! -f /etc/os-release ]; then
    print_error "Cannot determine OS"
    exit 1
fi

. /etc/os-release
if [ "$ID" != "ubuntu" ]; then
    print_error "This script is designed for Ubuntu only (detected: $ID)"
    exit 1
fi
print_status "Running on Ubuntu $VERSION_ID"

echo ""
echo "This script will configure your Azure VM with:"
echo "  1. System updates and timezone (UTC)"
echo "  2. Docker Engine and Docker Compose"
echo "  3. Azure CLI for managed identity"
echo "  4. fail2ban for SSH protection"
echo "  5. SSH hardening (key-only authentication)"
echo "  6. UFW firewall installation"
echo "  7. Deployment user ($DEPLOYMENT_USER)"
echo "  8. Systemd service for auto-start"
echo "  9. Docker log rotation"
echo "  10. UFW/Cloudflare IP configuration"
echo ""
print_warning "This will modify system configuration!"
echo ""
read -p "Continue? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
    echo "Setup cancelled."
    exit 0
fi

echo ""
echo "========================================="
echo "  Starting Setup"
echo "========================================="
echo ""

# Array of subscripts to run
SUBSCRIPTS=(
    "01-system-update.sh"
    "02-install-docker.sh"
    "03-install-azure-cli.sh"
    "04-configure-fail2ban.sh"
    "05-harden-ssh.sh"
    "06-install-ufw.sh"
    "07-create-deploy-user.sh"
    "08-create-systemd-service.sh"
    "09-configure-log-rotation.sh"
    "10-configure-ufw-cloudflare.sh"
)

# Track progress
TOTAL=${#SUBSCRIPTS[@]}
CURRENT=0
FAILED=()

# Run each subscript
for SUBSCRIPT in "${SUBSCRIPTS[@]}"; do
    CURRENT=$((CURRENT + 1))
    echo ""
    echo "========================================="
    echo "  Step $CURRENT/$TOTAL: $SUBSCRIPT"
    echo "========================================="
    echo ""

    if bash "$SCRIPT_DIR/setup/$SUBSCRIPT"; then
        print_status "Step $CURRENT/$TOTAL completed successfully"
    else
        print_error "Step $CURRENT/$TOTAL failed: $SUBSCRIPT"
        FAILED+=("$SUBSCRIPT")
    fi
done

echo ""
echo "========================================="
echo "  Setup Summary"
echo "========================================="
echo ""

if [ ${#FAILED[@]} -eq 0 ]; then
    print_status "All setup steps completed successfully!"
else
    print_error "Some steps failed:"
    for SCRIPT in "${FAILED[@]}"; do
        echo "  ✗ $SCRIPT"
    done
    echo ""
    print_info "You can re-run individual failed scripts from deploy/setup/"
    exit 1
fi

# Restart SSH to apply hardening
echo ""
print_info "Restarting SSH service to apply hardening..."
systemctl restart sshd
print_status "SSH service restarted"

echo ""
echo "========================================="
echo "  Next Steps"
echo "========================================="
echo ""
echo "1. Run deploy-keys.sh locally to generate SSH keys"
echo "2. Add public key to /home/$DEPLOYMENT_USER/.ssh/authorized_keys"
echo "3. Test SSH: ssh $DEPLOYMENT_USER@<VM_IP>"
echo "4. Copy application files to $APP_DIR/deploy"
echo "5. Set DOTENV_KEY in /etc/environment"
echo "6. Run UFW configuration:"
echo "   sudo python3 $APP_DIR/docker/scripts/ufw_cloudflare.py"
echo "7. Start application:"
echo "   sudo systemctl start docker-compose@isthetube"
echo ""
print_status "VM setup complete!"
