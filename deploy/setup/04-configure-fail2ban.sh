#!/usr/bin/env bash
# Install and configure fail2ban for SSH protection

set -euo pipefail

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"

require_root

echo "=== fail2ban Configuration ==="
echo ""

# Install fail2ban
print_info "Installing fail2ban..."
DEBIAN_FRONTEND=noninteractive apt-get install -y fail2ban

# Configure SSH jail
print_info "Configuring SSH jail (5 attempts, 10min ban)..."

# Backup existing jail config if present
JAIL_FILE="/etc/fail2ban/jail.d/sshd.conf"
if [ -f "$JAIL_FILE" ]; then
    BACKUP_TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    cp "$JAIL_FILE" "${JAIL_FILE}.backup.${BACKUP_TIMESTAMP}"
    print_info "Existing jail config backed up to ${JAIL_FILE}.backup.${BACKUP_TIMESTAMP}"
fi

cat > /etc/fail2ban/jail.d/sshd.conf <<'EOF'
[sshd]
enabled = true
port = 22
filter = sshd
logpath = /var/log/auth.log
maxretry = 5
bantime = 600
findtime = 600
EOF

print_status "fail2ban jail configured"

# Enable and start fail2ban
systemctl enable fail2ban
systemctl start fail2ban

# Wait a moment for fail2ban to initialize
sleep 2

# Verify fail2ban is running
if systemctl is-active --quiet fail2ban; then
    print_status "fail2ban is active"
    fail2ban-client status sshd || print_warning "SSH jail not yet active (will activate on first log entry)"
else
    print_error "fail2ban failed to start"
    exit 1
fi

echo ""
print_status "fail2ban configuration complete"
