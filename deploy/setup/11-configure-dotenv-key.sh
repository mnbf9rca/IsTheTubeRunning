#!/usr/bin/env bash
# Extract secrets from .env.vault and configure for application startup

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

echo "=== Extract Secrets and Configure Application ==="
echo ""

# Verify DOTENV_KEY is set (validated by setup-vm.sh)
if [ -z "${DOTENV_KEY:-}" ]; then
    print_error "DOTENV_KEY environment variable not set"
    print_info "This should have been validated by setup-vm.sh"
    exit 1
fi

SECRETS_FILE="/home/$DEPLOYMENT_USER/.env.secrets"

# Install uv if not present (needed for extraction)
# Install as deployment user to avoid PATH issues with sudo/root
if ! sudo -u "$DEPLOYMENT_USER" bash -c 'command -v uv' &>/dev/null && \
   ! sudo -u "$DEPLOYMENT_USER" bash -c 'test -x ~/.local/bin/uv' &>/dev/null; then
    print_status "Installing uv for credential extraction (as $DEPLOYMENT_USER)..."
    sudo -u "$DEPLOYMENT_USER" bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'

    # Verify installation at expected location
    if ! sudo -u "$DEPLOYMENT_USER" bash -c 'test -x ~/.local/bin/uv'; then
        print_error "Failed to install uv"
        print_info "Expected uv at /home/$DEPLOYMENT_USER/.local/bin/uv"
        exit 1
    fi

    print_status "uv installed successfully"
    echo ""
fi

# Extract POSTGRES_PASSWORD from .env.vault
print_info "Extracting database credentials from .env.vault..."
# This utility is at backend/app/utils/extract_db_credentials.py (well-tested utility)
# Run as deployment user to use their uv installation
POSTGRES_PASSWORD_OUTPUT=$(sudo -u "$DEPLOYMENT_USER" bash -c "cd '$APP_DIR/backend' && export DOTENV_KEY='$DOTENV_KEY' && ~/.local/bin/uv run python -m app.utils.extract_db_credentials password" 2>&1)
POSTGRES_PASSWORD_STATUS=$?

if [ $POSTGRES_PASSWORD_STATUS -ne 0 ]; then
    print_error "Failed to extract POSTGRES_PASSWORD from .env.vault"
    print_info "Command failed with exit code $POSTGRES_PASSWORD_STATUS"
    print_info "Output:"
    echo "$POSTGRES_PASSWORD_OUTPUT"
    print_info "Possible causes:"
    print_info "  - DOTENV_KEY is incorrect or invalid"
    print_info "  - .env.vault does not contain DATABASE_URL"
    print_info "  - DATABASE_URL does not contain a password"
    exit 1
fi

POSTGRES_PASSWORD="$POSTGRES_PASSWORD_OUTPUT"
if [ -z "${POSTGRES_PASSWORD}" ]; then
    print_error "Failed to extract POSTGRES_PASSWORD from .env.vault (empty value)"
    exit 1
fi

print_status "POSTGRES_PASSWORD extracted successfully"
print_info "Password length: ${#POSTGRES_PASSWORD} characters"
echo ""

# Extract CLOUDFLARE_TUNNEL_TOKEN from .env.vault
print_info "Extracting CLOUDFLARE_TUNNEL_TOKEN from .env.vault..."
# Use same utility as POSTGRES_PASSWORD for consistency (backend/app/utils/extract_db_credentials.py)
CLOUDFLARE_TUNNEL_TOKEN_OUTPUT=$(sudo -u "$DEPLOYMENT_USER" bash -c "cd '$APP_DIR/backend' && export DOTENV_KEY='$DOTENV_KEY' && ~/.local/bin/uv run python -m app.utils.extract_db_credentials tunnel_token" 2>&1)
CLOUDFLARE_TUNNEL_TOKEN_STATUS=$?

if [ $CLOUDFLARE_TUNNEL_TOKEN_STATUS -ne 0 ]; then
    print_error "Failed to extract CLOUDFLARE_TUNNEL_TOKEN from .env.vault"
    print_info "Command failed with exit code $CLOUDFLARE_TUNNEL_TOKEN_STATUS"
    print_info "Output:"
    echo "$CLOUDFLARE_TUNNEL_TOKEN_OUTPUT"
    print_info "Possible causes:"
    print_info "  - DOTENV_KEY is incorrect or invalid"
    print_info "  - .env.vault does not contain CLOUDFLARE_TUNNEL_TOKEN"
    exit 1
fi

CLOUDFLARE_TUNNEL_TOKEN="$CLOUDFLARE_TUNNEL_TOKEN_OUTPUT"
if [ -z "${CLOUDFLARE_TUNNEL_TOKEN}" ]; then
    print_error "Failed to extract CLOUDFLARE_TUNNEL_TOKEN from .env.vault (empty value)"
    exit 1
fi

print_status "CLOUDFLARE_TUNNEL_TOKEN extracted successfully"
print_info "Token length: ${#CLOUDFLARE_TUNNEL_TOKEN} characters"
echo ""

# DOTENV_KEY is validated by setup-vm.sh, so it's guaranteed to be set here
print_info "Configuring application secrets..."
print_info "All credentials extracted from .env.vault (single source of truth)"

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
# Location: $SECRETS_FILE (outside git clone for security)
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
