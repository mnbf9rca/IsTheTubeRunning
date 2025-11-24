#!/usr/bin/env bash
# Harden SSH configuration for security

set -euo pipefail

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"

require_root

echo "=== SSH Hardening ==="
echo ""

SSH_CONFIG="/etc/ssh/sshd_config"

# Backup original config
if [ ! -f "${SSH_CONFIG}.original" ]; then
    print_info "Backing up original SSH config..."
    cp "$SSH_CONFIG" "${SSH_CONFIG}.original"
fi

cp "$SSH_CONFIG" "${SSH_CONFIG}.backup"
print_info "Current config backed up to ${SSH_CONFIG}.backup"

# Apply SSH hardening settings
print_info "Applying SSH hardening settings..."
sed -i 's/#\?PasswordAuthentication.*/PasswordAuthentication no/' "$SSH_CONFIG"
sed -i 's/#\?PubkeyAuthentication.*/PubkeyAuthentication yes/' "$SSH_CONFIG"
sed -i 's/#\?PermitRootLogin.*/PermitRootLogin no/' "$SSH_CONFIG"

# Handle both old and new directive names for keyboard-interactive authentication
# ChallengeResponseAuthentication (deprecated in OpenSSH 8.4+)
# KbdInteractiveAuthentication (new name in OpenSSH 8.4+, Ubuntu 24.04 default)
sed -i 's/#\?ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' "$SSH_CONFIG"
sed -i 's/#\?KbdInteractiveAuthentication.*/KbdInteractiveAuthentication no/' "$SSH_CONFIG"

# Add KbdInteractiveAuthentication if not present (for newer OpenSSH)
if ! grep -q "^KbdInteractiveAuthentication" "$SSH_CONFIG"; then
    echo "KbdInteractiveAuthentication no" >> "$SSH_CONFIG"
fi

# Test SSH configuration
print_info "Testing SSH configuration..."
if sshd -t; then
    print_status "SSH configuration is valid"
else
    print_error "SSH configuration test failed - restoring backup"
    cp "${SSH_CONFIG}.backup" "$SSH_CONFIG"
    exit 1
fi

# Show what changed
echo ""
print_info "SSH hardening changes:"
echo "  ✓ PasswordAuthentication: no (key-only auth)"
echo "  ✓ PubkeyAuthentication: yes"
echo "  ✓ PermitRootLogin: no"
echo "  ✓ KbdInteractiveAuthentication: no (disables keyboard-interactive auth)"

print_warning "SSH will be restarted by setup-vm.sh after deployment user is configured"

echo ""
print_status "SSH hardening complete"
