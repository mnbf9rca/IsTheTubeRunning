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

# Helper function to extract credentials with retry logic
# Arguments: $1=credential_name, $2=validation_regex (e.g., "^ey" for JWT tokens)
# Output: Credential value on stdout, status messages on stderr
extract_credential() {
    local CREDENTIAL_NAME="$1"
    local VALIDATION_REGEX="$2"
    local ATTEMPT=0
    local MAX_ATTEMPTS=2

    while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
        ATTEMPT=$((ATTEMPT + 1))

        if [ $ATTEMPT -eq 1 ]; then
            print_info "Extracting $CREDENTIAL_NAME from .env.vault..." >&2
        else
            print_warning "Retry $ATTEMPT/$MAX_ATTEMPTS for $CREDENTIAL_NAME..." >&2
        fi

        # Run extraction, capturing all output
        EXTRACTION_OUTPUT=$(sudo -u "$DEPLOYMENT_USER" bash -c "cd '$APP_DIR/backend' && export DOTENV_KEY='$DOTENV_KEY' && ~/.local/bin/uv run python -m app.utils.extract_db_credentials $CREDENTIAL_NAME" 2>&1)
        EXTRACTION_STATUS=$?

        # Count output lines - should be exactly 1 (the credential)
        LINE_COUNT=$(echo "$EXTRACTION_OUTPUT" | wc -l)

        # If more than 1 line, show output for troubleshooting
        if [ "$LINE_COUNT" -gt 1 ]; then
            print_warning "Extraction returned $LINE_COUNT lines (expected 1)" >&2
            print_info "Full output shown for troubleshooting:" >&2
            echo "$EXTRACTION_OUTPUT" >&2
            echo "" >&2

            if [ $ATTEMPT -lt $MAX_ATTEMPTS ]; then
                print_info "Retrying (packages may be installing on first run)..." >&2
                sleep 2
                continue
            else
                print_error "Failed after $MAX_ATTEMPTS attempts" >&2
                return 1
            fi
        fi

        # Check exit status
        if [ $EXTRACTION_STATUS -ne 0 ]; then
            print_error "Extraction failed with exit code $EXTRACTION_STATUS" >&2
            echo "$EXTRACTION_OUTPUT" >&2
            return 1
        fi

        # Validate credential format
        if [ -z "$EXTRACTION_OUTPUT" ]; then
            print_error "Extracted credential is empty" >&2
            return 1
        elif [[ ! "$EXTRACTION_OUTPUT" =~ $VALIDATION_REGEX ]]; then
            print_error "Credential doesn't match expected format" >&2
            print_info "Expected pattern: $VALIDATION_REGEX" >&2
            print_info "Got: ${EXTRACTION_OUTPUT:0:20}..." >&2
            return 1
        fi

        # Success! Status to stderr, credential to stdout
        print_status "$CREDENTIAL_NAME extracted successfully (${#EXTRACTION_OUTPUT} chars)" >&2
        echo "$EXTRACTION_OUTPUT"
        return 0
    done

    return 1
}

# Extract CLOUDFLARE_TUNNEL_TOKEN (JWT format - starts with 'ey')
if ! CLOUDFLARE_TUNNEL_TOKEN=$(extract_credential "tunnel_token" "^ey"); then
    exit 1
fi

# Extract POSTGRES_PASSWORD (alphanumeric)
if ! POSTGRES_PASSWORD=$(extract_credential "password" "^[a-zA-Z0-9]"); then
    exit 1
fi

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
