#!/usr/bin/env bash
# Install Azure CLI for managed identity authentication

set -euo pipefail

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"

require_root

echo "=== Azure CLI Installation ==="
echo ""

# Check if Azure CLI is already installed
if command_exists az; then
    AZ_VERSION=$(az version --output tsv --query '["azure-cli"]')
    print_warning "Azure CLI is already installed: $AZ_VERSION"
    read -p "Reinstall Azure CLI? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
        print_info "Skipping Azure CLI installation"
        exit 0
    fi
fi

# Install Azure CLI using official installation script
print_info "Installing Azure CLI..."
curl -sL https://aka.ms/InstallAzureCLIDeb | bash

# Verify installation
if command_exists az; then
    print_status "Azure CLI installed successfully"
    az version --output table
else
    print_warning "Azure CLI installation may have issues"
    print_info "This is non-critical for deployment - backup script can use managed identity"
fi

echo ""
print_status "Azure CLI installation complete"
