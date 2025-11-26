#!/usr/bin/env bash
# Create deployment user with docker access

set -euo pipefail

# Source common functions and Azure config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"
# shellcheck source=../azure-config.sh
source "$SCRIPT_DIR/../azure-config.sh"

require_root

echo "=== Deployment User Setup ==="
echo ""

# Create deployment user
if id "$DEPLOYMENT_USER" &>/dev/null; then
    print_warning "User $DEPLOYMENT_USER already exists"
else
    print_info "Creating user $DEPLOYMENT_USER..."
    useradd -m -s /bin/bash "$DEPLOYMENT_USER"
    print_status "User $DEPLOYMENT_USER created"
fi

# Ensure home directory ownership is correct (idempotency)
print_info "Ensuring home directory ownership..."
chown "$DEPLOYMENT_USER:$DEPLOYMENT_USER" "/home/$DEPLOYMENT_USER"
print_status "Home directory ownership verified"

# Add to docker group
print_info "Adding $DEPLOYMENT_USER to docker group..."
usermod -aG docker "$DEPLOYMENT_USER"
print_status "User added to docker group"

# Create application directory
if [ ! -d "$APP_DIR" ]; then
    print_info "Creating application directory: $APP_DIR..."
    mkdir -p "$APP_DIR"
    chown -R "$DEPLOYMENT_USER:$DEPLOYMENT_USER" "$APP_DIR"
    print_status "Application directory created"
else
    print_warning "Application directory already exists: $APP_DIR"
    chown -R "$DEPLOYMENT_USER:$DEPLOYMENT_USER" "$APP_DIR"
fi

# Create .ssh directory
DEPLOY_SSH_DIR="/home/$DEPLOYMENT_USER/.ssh"
if [ ! -d "$DEPLOY_SSH_DIR" ]; then
    print_info "Creating SSH directory for $DEPLOYMENT_USER..."
    mkdir -p "$DEPLOY_SSH_DIR"
    touch "$DEPLOY_SSH_DIR/authorized_keys"
    chown -R "$DEPLOYMENT_USER:$DEPLOYMENT_USER" "$DEPLOY_SSH_DIR"
    chmod 700 "$DEPLOY_SSH_DIR"
    chmod 600 "$DEPLOY_SSH_DIR/authorized_keys"
    print_status "SSH directory created"
else
    print_warning "SSH directory already exists for $DEPLOYMENT_USER"
fi

echo ""
print_info "Deployment user configuration:"
echo "  User: $DEPLOYMENT_USER"
echo "  Home: /home/$DEPLOYMENT_USER"
echo "  App directory: $APP_DIR"
echo "  Docker access: yes"
echo "  SSH directory: $DEPLOY_SSH_DIR"
echo ""
print_info "Next: Add public key to $DEPLOY_SSH_DIR/authorized_keys"

echo ""
print_status "Deployment user setup complete"
