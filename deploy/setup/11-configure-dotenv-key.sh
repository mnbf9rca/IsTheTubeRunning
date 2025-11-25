#!/usr/bin/env bash
# Configure DOTENV_KEY and CLOUDFLARE_TUNNEL_TOKEN for application startup

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

echo "=== Application Secrets Configuration ==="
echo ""

SECRETS_FILE="/home/$DEPLOYMENT_USER/.env.secrets"

# Verify POSTGRES_PASSWORD is set (exported by script 10.5)
if [ -z "${POSTGRES_PASSWORD:-}" ]; then
    print_error "POSTGRES_PASSWORD not set - ensure script 10.5 ran successfully"
    exit 1
fi

# Verify CLOUDFLARE_TUNNEL_TOKEN is set (exported by script 10.5)
if [ -z "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]; then
    print_error "CLOUDFLARE_TUNNEL_TOKEN not set - ensure script 10.5 ran successfully"
    exit 1
fi

# DOTENV_KEY is validated by setup-vm.sh, so it's guaranteed to be set here
print_info "Configuring application secrets..."
print_info "Using credentials extracted from .env.vault by script 10.5"

# Check if secrets file already exists
if [ -f "$SECRETS_FILE" ]; then
    # Backup existing file with timestamp
    BACKUP_TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    BACKUP_FILE="${SECRETS_FILE}.backup.${BACKUP_TIMESTAMP}"
    cp "$SECRETS_FILE" "$BACKUP_FILE"
    print_status "Backup created: $BACKUP_FILE"
fi

print_info "Writing secrets to $SECRETS_FILE..."

# Write secrets to file
cat > "$SECRETS_FILE" <<EOF
# Application secrets for IsTheTubeRunning production deployment
# Location: /home/$DEPLOYMENT_USER/.env.secrets (outside git clone for security)
# Loaded by: docker-compose.prod.yml env_file directive

# DOTENV_KEY: Decrypts .env.vault containing application configuration
DOTENV_KEY=${DOTENV_KEY}

# CLOUDFLARE_TUNNEL_TOKEN: Authenticates to Cloudflare Tunnel for ingress
CLOUDFLARE_TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}

# POSTGRES_PASSWORD: PostgreSQL database password (extracted from .env.vault)
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
EOF

# Set secure permissions (read/write by owner only)
chmod 600 "$SECRETS_FILE"

# Set ownership to deployment user
chown "$DEPLOYMENT_USER:$DEPLOYMENT_USER" "$SECRETS_FILE"

print_status "Secrets written to $SECRETS_FILE"
print_status "  - DOTENV_KEY: configured ✓"
print_status "  - CLOUDFLARE_TUNNEL_TOKEN: configured ✓ (extracted from .env.vault)"
print_status "  - POSTGRES_PASSWORD: configured ✓ (extracted from .env.vault)"
print_status "Permissions: 600 (owner read/write only)"
print_status "Owner: $DEPLOYMENT_USER:$DEPLOYMENT_USER"
echo ""
print_status "All credentials synchronized with .env.vault (single source of truth)"
print_info "No manual sync required - credentials extracted deterministically"

# Reload systemd to pick up new environment variable
systemctl daemon-reload
print_status "Systemd environment reloaded"

echo ""
print_status "Application secrets configuration complete"
