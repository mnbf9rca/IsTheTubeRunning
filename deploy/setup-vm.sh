#!/usr/bin/env bash
# Setup Azure VM with Docker, security hardening, and deployment tooling
# Orchestrates modular setup subscripts

set -euo pipefail

# Parse command line arguments
SKIP_CONFIRM=false
GIT_BRANCH=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -b|--branch)
            GIT_BRANCH="$2"
            shift 2
            ;;
        -y|--yes)
            SKIP_CONFIRM=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -b, --branch BRANCH  Git branch to deploy (required)"
            echo "  -y, --yes            Skip confirmation prompt"
            echo "  -h, --help           Show this help message"
            echo ""
            echo "Example:"
            echo "  DOTENV_KEY=\"\$DOTENV_KEY_PRODUCTION\" sudo -E ./setup-vm.sh --branch main"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=./setup/common.sh
source "$SCRIPT_DIR/setup/common.sh"

require_root

# Validate required branch argument
if [ -z "$GIT_BRANCH" ]; then
    print_error "Branch argument is required"
    echo ""
    echo "Usage: $0 --branch BRANCH [OPTIONS]"
    echo ""
    echo "Example:"
    echo "  DOTENV_KEY=\"\$DOTENV_KEY_PRODUCTION\" sudo -E ./setup-vm.sh --branch main"
    exit 1
fi

echo "========================================="
echo "  IsTheTubeRunning - VM Setup"
echo "========================================="
echo ""
echo "Deployment branch: $GIT_BRANCH"
echo ""
echo "Checking prerequisites..."
echo ""

# Validate DOTENV_KEY is provided
if [ -z "${DOTENV_KEY:-}" ]; then
    print_error "DOTENV_KEY environment variable is required"
    echo ""
    echo "The application cannot run without DOTENV_KEY."
    echo "CLOUDFLARE_TUNNEL_TOKEN and POSTGRES_PASSWORD will be extracted from .env.vault."
    echo ""
    echo "Run setup with:"
    echo "  DOTENV_KEY=\"\$DOTENV_KEY_PRODUCTION\" sudo -E ./setup-vm.sh --branch main"
    exit 1
fi

# Validate DOTENV_KEY format
if [[ ! "$DOTENV_KEY" =~ ^dotenv:// ]]; then
    print_error "DOTENV_KEY must start with 'dotenv://'"
    echo ""
    echo "Expected format: dotenv://:key_...@dotenvx.com/vault/.env.vault?environment=production"
    echo "Received: ${DOTENV_KEY:0:20}..."
    exit 1
fi

print_status "DOTENV_KEY validated"
print_info "CLOUDFLARE_TUNNEL_TOKEN and POSTGRES_PASSWORD will be extracted from .env.vault during setup"
echo ""

# Check internet connectivity (skip if ping not available on minimal image)
if command -v ping &> /dev/null; then
    if ping -c 1 8.8.8.8 &> /dev/null; then
        print_status "Internet connectivity OK"
    else
        print_error "No internet connectivity"
        exit 1
    fi
else
    print_info "Skipping connectivity check (ping not available on minimal image)"
fi

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
echo "  7. Deployment user"
echo "  8. Systemd service for auto-start"
echo "  9. Docker log rotation"
echo "  10. UFW/SSH firewall configuration"
echo "  11. DOTENV_KEY and CLOUDFLARE_TUNNEL_TOKEN configuration"
echo "  12. Automatic security updates (unattended-upgrades)"
echo ""
print_warning "This will modify system configuration!"
echo ""

if [ "$SKIP_CONFIRM" = false ]; then
    read -p "Continue? (y/n): " -r
    if [[ ! $REPLY =~ ^[Yy](es)?$ ]]; then
        echo "Setup cancelled."
        exit 0
    fi
fi

echo ""
echo "========================================="
echo "  Starting Setup"
echo "========================================="
echo ""

# Step 1/12: Run system update first (installs jq needed for azure-config.sh)
echo ""
echo "========================================="
echo "  Step 1/12: 01-system-update.sh"
echo "========================================="
echo ""

if bash "$SCRIPT_DIR/setup/01-system-update.sh"; then
    print_status "Step 1/12 completed successfully"
else
    print_error "Step 1/12 failed: 01-system-update.sh"
    print_error "Cannot continue with remaining setup steps"
    exit 1
fi

# Load Azure configuration (requires jq from step 1)
# shellcheck source=./azure-config.sh
source "$SCRIPT_DIR/azure-config.sh"

# Declare required configuration for this script
validate_required_config "DEPLOYMENT_USER" "APP_DIR" || exit 1

# Array of remaining subscripts to run
SUBSCRIPTS=(
    "02-install-docker.sh"
    "03-install-azure-cli.sh"
    "04-configure-fail2ban.sh"
    "05-harden-ssh.sh"
    "06-install-ufw.sh"
    "07-create-deploy-user.sh"
    "08-create-systemd-service.sh"
    "09-configure-log-rotation.sh"
    "10-configure-ufw-cloudflare.sh"
    "10.5-clone-repo.sh"
    "11-configure-dotenv-key.sh"
    "12-configure-unattended-upgrades.sh"
)

# Track progress (starting from step 2)
TOTAL=13
CURRENT=1

# Run each subscript
for SUBSCRIPT in "${SUBSCRIPTS[@]}"; do
    CURRENT=$((CURRENT + 1))
    echo ""
    echo "========================================="
    echo "  Step $CURRENT/$TOTAL: $SUBSCRIPT"
    echo "========================================="
    echo ""

    # Script 10.5 requires branch argument
    if [ "$SUBSCRIPT" = "10.5-clone-repo.sh" ]; then
        bash "$SCRIPT_DIR/setup/$SUBSCRIPT" "$GIT_BRANCH"
        SCRIPT_EXIT_CODE=$?
    else
        bash "$SCRIPT_DIR/setup/$SUBSCRIPT"
        SCRIPT_EXIT_CODE=$?
    fi

    if [ $SCRIPT_EXIT_CODE -eq 0 ]; then
        print_status "Step $CURRENT/$TOTAL completed successfully"
    else
        print_error "Step $CURRENT/$TOTAL failed: $SUBSCRIPT"
        print_error "Cannot continue with remaining setup steps"
        print_info "Fix the issue and re-run setup-vm.sh to continue"
        exit 1
    fi
done

echo ""
echo "========================================="
echo "  Setup Summary"
echo "========================================="
echo ""
print_status "All setup steps completed successfully!"

# Restart SSH to apply hardening
echo ""
print_info "Restarting SSH service to apply hardening..."
systemctl restart ssh
print_status "SSH service restarted"

echo ""
echo "========================================="
echo "  VM Setup Complete"
echo "========================================="
echo ""
print_status "Base VM configuration finished!"
echo ""
echo "Next steps are shown in the output of provision-azure-vm.sh"
echo "(Generate deployment keys, deploy application code, start service)"
echo ""
