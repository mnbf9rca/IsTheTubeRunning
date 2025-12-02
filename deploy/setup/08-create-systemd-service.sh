#!/usr/bin/env bash
# Create systemd service for docker-compose auto-start

set -euo pipefail

# Source common functions and Azure config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"
# shellcheck source=../azure-config.sh
source "$SCRIPT_DIR/../azure-config.sh"

require_root

echo "=== Systemd Service Creation ==="
echo ""

SERVICE_FILE="/etc/systemd/system/docker-compose@isthetube.service"

# Backup existing service file if present
if [ -f "$SERVICE_FILE" ]; then
    BACKUP_TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    cp "$SERVICE_FILE" "${SERVICE_FILE}.backup.${BACKUP_TIMESTAMP}"
    print_info "Existing service file backed up to ${SERVICE_FILE}.backup.${BACKUP_TIMESTAMP}"
fi

print_info "Creating systemd service: $SERVICE_FILE..."
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Docker Compose Application Service for IsTheTubeRunning
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR/deploy
User=$DEPLOYMENT_USER
Group=$DEPLOYMENT_USER
EnvironmentFile=/home/$DEPLOYMENT_USER/.env.secrets
# Note: EnvironmentFile is required for docker-compose variable substitution (e.g., \${DOTENV_PRIVATE_KEY_PRODUCTION}, \${POSTGRES_PASSWORD}, etc.)
# These variables must be present in the systemd environment for docker-compose to substitute them.
# The env_file directive in docker-compose.prod.yml makes these variables available inside the containers.

# Pull latest images and start services
ExecStartPre=/usr/bin/docker compose -f docker-compose.prod.yml pull
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up --no-log-prefix

# Stop services gracefully (SIGTERM), containers remain in stopped state for faster restart
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml stop

# Restart policy
Restart=on-failure
RestartSec=10s

# Timeouts
TimeoutStartSec=600
TimeoutStopSec=60

[Install]
WantedBy=multi-user.target
EOF

print_status "Service file created"

# Reload systemd
print_info "Reloading systemd daemon..."
systemctl daemon-reload

# Enable service
print_info "Enabling service..."
systemctl enable docker-compose@isthetube

print_status "Service enabled (will start on boot)"

# Check DOTENV_PRIVATE_KEY_PRODUCTION configuration (warning only)
echo ""
print_info "Checking DOTENV_PRIVATE_KEY_PRODUCTION configuration..."
SECRETS_FILE="/home/$DEPLOYMENT_USER/.env.secrets"
if [[ ! -f "$SECRETS_FILE" ]] || ! grep -q "^DOTENV_PRIVATE_KEY_PRODUCTION=" "$SECRETS_FILE" 2>/dev/null; then
    print_warning "DOTENV_PRIVATE_KEY_PRODUCTION not found in $SECRETS_FILE"
    print_warning "The systemd service will not start until this is configured"
    print_info "This will be configured automatically by script 11-configure-dotenv-key.sh"
else
    print_status "DOTENV_PRIVATE_KEY_PRODUCTION is configured"
fi

echo ""
print_warning "Service will NOT start until application is deployed to $APP_DIR/deploy"
print_info "To start manually after deployment:"
print_info "  sudo systemctl start docker-compose@isthetube"

echo ""
print_status "Systemd service creation complete"
