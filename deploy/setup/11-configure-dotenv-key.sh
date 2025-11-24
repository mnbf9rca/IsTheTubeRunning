#!/usr/bin/env bash
# Configure DOTENV_KEY for application startup

set -euo pipefail

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"
# shellcheck source=../azure-config.sh
source "$SCRIPT_DIR/../azure-config.sh"

# Declare required configuration
validate_required_config "DEPLOYMENT_USER" "APP_DIR" || exit 1

require_root

echo "=== DOTENV_KEY Configuration ==="
echo ""

SECRETS_FILE="$APP_DIR/.env.secrets"

# DOTENV_KEY is validated by setup-vm.sh, so it's guaranteed to be set here
print_info "Configuring DOTENV_KEY..."

# Create APP_DIR if it doesn't exist
if [ ! -d "$APP_DIR" ]; then
    mkdir -p "$APP_DIR"
    print_status "Created directory: $APP_DIR"
fi

# Check if secrets file already exists
if [ -f "$SECRETS_FILE" ]; then
    # Backup existing file with timestamp
    BACKUP_TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    BACKUP_FILE="${SECRETS_FILE}.backup.${BACKUP_TIMESTAMP}"
    cp "$SECRETS_FILE" "$BACKUP_FILE"
    print_status "Backup created: $BACKUP_FILE"
fi

# Write DOTENV_KEY to secrets file
echo "DOTENV_KEY=${DOTENV_KEY}" > "$SECRETS_FILE"

# Set secure permissions (read/write by owner only)
chmod 600 "$SECRETS_FILE"

# Set ownership to deployment user
chown "$DEPLOYMENT_USER:$DEPLOYMENT_USER" "$SECRETS_FILE"

print_status "DOTENV_KEY written to $SECRETS_FILE"
print_status "Permissions: 600 (owner read/write only)"
print_status "Owner: $DEPLOYMENT_USER:$DEPLOYMENT_USER"

# Reload systemd to pick up new environment variable
systemctl daemon-reload
print_status "Systemd environment reloaded"

echo ""
print_status "DOTENV_KEY configuration complete"
