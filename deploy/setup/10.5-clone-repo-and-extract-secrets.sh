#!/usr/bin/env bash
# Clone repository and extract database credentials from .env.vault
#
# This script:
# 1. Clones the IsTheTubeRunning repository to APP_DIR at specified branch
# 2. Extracts POSTGRES_PASSWORD from .env.vault using existing utility
# 3. Exports POSTGRES_PASSWORD for use by subsequent setup scripts
#
# Prerequisites:
#   - DOTENV_KEY environment variable set (for .env.vault decryption)
#   - DEPLOYMENT_USER configured in azure-config.json
#   - APP_DIR configured in azure-config.json
#
# Arguments:
#   $1: Git branch to clone (required, no default)
#
# Exports:
#   POSTGRES_PASSWORD: Extracted from DATABASE_URL in .env.vault

set -euo pipefail

# Validate branch argument
if [ $# -ne 1 ]; then
    echo "ERROR: Branch argument required" >&2
    echo "Usage: $0 <branch>" >&2
    echo "Example: $0 main" >&2
    exit 1
fi

GIT_BRANCH="$1"

# Source common functions and Azure config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"
# shellcheck source=../azure-config.sh
source "$SCRIPT_DIR/../azure-config.sh"

# Declare required configuration
validate_required_config "DEPLOYMENT_USER" "APP_DIR" || exit 1

require_root

echo "=== Repository Clone and Credential Extraction ==="
echo ""

# Verify DOTENV_KEY is set (validated by setup-vm.sh)
if [ -z "${DOTENV_KEY:-}" ]; then
    print_error "DOTENV_KEY environment variable not set"
    print_info "This should have been validated by setup-vm.sh"
    exit 1
fi

# Check if repository directory exists
if [ -d "$APP_DIR" ] && [ "$(ls -A "$APP_DIR" 2>/dev/null)" ]; then
    print_status "Repository directory already exists: $APP_DIR"
    print_info "Updating to branch: $GIT_BRANCH"
    echo ""

    # Fetch latest changes from origin (show output for debugging)
    print_info "Fetching latest changes from origin..."
    if sudo -u "$DEPLOYMENT_USER" git -C "$APP_DIR" fetch origin; then
        print_status "Fetched latest changes from origin"
    else
        print_error "Failed to fetch from origin"
        exit 1
    fi
    echo ""

    # Checkout the requested branch (will track remote if not local)
    print_info "Checking out branch: $GIT_BRANCH"
    if sudo -u "$DEPLOYMENT_USER" git -C "$APP_DIR" checkout "$GIT_BRANCH"; then
        print_status "Checked out branch: $GIT_BRANCH"
    else
        echo ""
        print_error "Failed to checkout branch: $GIT_BRANCH"
        print_info "Branch may not exist on remote. Available remote branches:"
        sudo -u "$DEPLOYMENT_USER" git -C "$APP_DIR" branch -r | grep -v HEAD
        echo ""
        print_info "Push the branch to GitHub first:"
        print_info "  git push origin $GIT_BRANCH"
        exit 1
    fi
    echo ""

    # Pull latest changes for this branch
    print_info "Pulling latest changes for $GIT_BRANCH..."
    if sudo -u "$DEPLOYMENT_USER" git -C "$APP_DIR" pull origin "$GIT_BRANCH"; then
        print_status "Repository updated to latest $GIT_BRANCH"
    else
        print_error "Failed to pull latest changes"
        exit 1
    fi
else
    print_info "Cloning repository to $APP_DIR (branch: $GIT_BRANCH)..."
    echo ""

    # Create parent directory if it doesn't exist
    mkdir -p "$(dirname "$APP_DIR")"

    # Clone as deployment user with specific branch (show output for debugging)
    if sudo -u "$DEPLOYMENT_USER" git clone --branch "$GIT_BRANCH" https://github.com/mnbf9rca/IsTheTubeRunning.git "$APP_DIR"; then
        print_status "Repository cloned successfully (branch: $GIT_BRANCH)"
    else
        echo ""
        print_error "Failed to clone branch: $GIT_BRANCH"
        print_info "Branch may not exist on remote"
        print_info "Push the branch to GitHub first:"
        print_info "  git push origin $GIT_BRANCH"
        exit 1
    fi
fi

# Extract POSTGRES_PASSWORD from .env.vault
print_info "Extracting database credentials from .env.vault..."

cd "$APP_DIR/backend"

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
fi

# Use Python utility to extract credentials
# Note: This requires DOTENV_KEY to decrypt .env.vault
print_info "Running credential extraction utility..."

# Extract POSTGRES_PASSWORD using existing tested utility
# This utility is at backend/app/utils/extract_db_credentials.py (100% test coverage)
# Run as deployment user to use their uv installation
POSTGRES_PASSWORD=$(sudo -u "$DEPLOYMENT_USER" bash -c "cd '$APP_DIR/backend' && export DOTENV_KEY='$DOTENV_KEY' && ~/.local/bin/uv run python -m app.utils.extract_db_credentials password")

if [ -z "${POSTGRES_PASSWORD}" ]; then
    print_error "Failed to extract POSTGRES_PASSWORD from .env.vault"
    print_info "Possible causes:"
    print_info "  - DOTENV_KEY is incorrect or invalid"
    print_info "  - .env.vault does not contain DATABASE_URL"
    print_info "  - DATABASE_URL does not contain a password"
    exit 1
fi

print_status "POSTGRES_PASSWORD extracted successfully"
print_info "Password length: ${#POSTGRES_PASSWORD} characters"

# Extract CLOUDFLARE_TUNNEL_TOKEN from .env.vault
print_info "Extracting CLOUDFLARE_TUNNEL_TOKEN from .env.vault..."
CLOUDFLARE_TUNNEL_TOKEN=$(sudo -u "$DEPLOYMENT_USER" bash -c "cd '$APP_DIR/backend' && export DOTENV_KEY='$DOTENV_KEY' && ~/.local/bin/uv run python -c \"from dotenv_vault import load_dotenv; import os; load_dotenv(); print(os.getenv('CLOUDFLARE_TUNNEL_TOKEN', ''))\"")

if [ -z "${CLOUDFLARE_TUNNEL_TOKEN}" ]; then
    print_error "Failed to extract CLOUDFLARE_TUNNEL_TOKEN from .env.vault"
    print_info "Possible causes:"
    print_info "  - DOTENV_KEY is incorrect or invalid"
    print_info "  - .env.vault does not contain CLOUDFLARE_TUNNEL_TOKEN"
    exit 1
fi

print_status "CLOUDFLARE_TUNNEL_TOKEN extracted successfully"
print_info "Token length: ${#CLOUDFLARE_TUNNEL_TOKEN} characters"

# Write credentials to temporary file for setup-vm.sh to source
# (exports don't persist across subscript invocations since each runs in a subshell)
TEMP_SECRETS_FILE="/tmp/setup-secrets.env"
cat > "$TEMP_SECRETS_FILE" <<EOF
# Temporary credentials extracted from .env.vault by script 10.5
# Will be sourced by setup-vm.sh and passed to script 11
export POSTGRES_PASSWORD='${POSTGRES_PASSWORD}'
export CLOUDFLARE_TUNNEL_TOKEN='${CLOUDFLARE_TUNNEL_TOKEN}'
EOF

chmod 600 "$TEMP_SECRETS_FILE"
print_status "All credentials extracted from .env.vault (single source of truth)"
print_info "Credentials written to $TEMP_SECRETS_FILE for setup-vm.sh to source"

echo ""
print_status "Repository clone and credential extraction complete"
print_info "POSTGRES_PASSWORD and CLOUDFLARE_TUNNEL_TOKEN are now available for script 11-configure-dotenv-key.sh"
