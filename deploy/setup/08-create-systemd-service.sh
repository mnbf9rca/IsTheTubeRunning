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
EnvironmentFile=/etc/environment

# Pull latest images and start services
ExecStartPre=/usr/bin/docker compose -f docker-compose.prod.yml pull
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up --no-log-prefix

# Stop services
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down

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

# Validate DOTENV_KEY is configured
echo ""
print_info "Validating DOTENV_KEY configuration..."
if [[ ! -f /etc/environment ]]; then
    print_error "/etc/environment not found"
    print_error "The systemd service requires DOTENV_KEY to be set in /etc/environment"
    print_error "Add it with: echo 'DOTENV_KEY=your_key' | sudo tee -a /etc/environment"
    exit 1
fi

if ! grep -q "^DOTENV_KEY=" /etc/environment; then
    print_error "DOTENV_KEY not found in /etc/environment"
    print_error "The systemd service requires this variable to decrypt application secrets"
    print_error "Add it with: echo 'DOTENV_KEY=your_key' | sudo tee -a /etc/environment"
    exit 1
fi

print_status "DOTENV_KEY is configured"

echo ""
print_warning "Service will NOT start until application is deployed to $APP_DIR/deploy"
print_info "To start manually after deployment:"
print_info "  sudo systemctl start docker-compose@isthetube"

echo ""
print_status "Systemd service creation complete"
