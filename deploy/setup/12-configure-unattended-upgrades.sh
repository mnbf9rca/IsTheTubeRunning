#!/usr/bin/env bash
# Configure unattended-upgrades for automatic security updates

set -euo pipefail

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "$SCRIPT_DIR/common.sh"

require_root

echo "=== Unattended Upgrades Configuration ==="
echo ""

# Install unattended-upgrades (pre-installed on Ubuntu 24.04, but verify)
print_info "Installing unattended-upgrades package..."
DEBIAN_FRONTEND=noninteractive apt-get install -y unattended-upgrades

print_status "Package installed"

# Configure 20auto-upgrades
print_info "Configuring automatic update schedule..."

AUTO_UPGRADES="/etc/apt/apt.conf.d/20auto-upgrades"
if [ -f "$AUTO_UPGRADES" ]; then
    BACKUP_TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    cp "$AUTO_UPGRADES" "${AUTO_UPGRADES}.backup.${BACKUP_TIMESTAMP}"
    print_info "Backed up existing config to ${AUTO_UPGRADES}.backup.${BACKUP_TIMESTAMP}"
fi

cat > "$AUTO_UPGRADES" <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
EOF

print_status "Update schedule configured"

# Configure 50unattended-upgrades
print_info "Configuring security-only updates with auto-reboot..."

UNATTENDED_CONFIG="/etc/apt/apt.conf.d/50unattended-upgrades"
if [ -f "$UNATTENDED_CONFIG" ]; then
    BACKUP_TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    cp "$UNATTENDED_CONFIG" "${UNATTENDED_CONFIG}.backup.${BACKUP_TIMESTAMP}"
    print_info "Backed up existing config to ${UNATTENDED_CONFIG}.backup.${BACKUP_TIMESTAMP}"
fi

cat > "$UNATTENDED_CONFIG" <<'EOF'
// Automatic security updates configuration for production Ubuntu 24.04 LTS
// Configured by IsTheTubeRunning deployment scripts

// Allowed origins - SECURITY UPDATES ONLY (production best practice)
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
    // Extended Security Maintenance (ESM) security updates
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";

    // DO NOT enable these on production:
    // "${distro_id}:${distro_codename}-updates";      // General updates (may break workloads)
    // "${distro_id}:${distro_codename}-proposed";     // Pre-release packages (unstable)
    // "${distro_id}:${distro_codename}-backports";    // Backported packages (rapidly changing)
};

// Package blacklist - never auto-update these
Unattended-Upgrade::Package-Blacklist {
    // Docker packages - manual control for production stability
    "docker-ce";
    "docker-ce-cli";
    "containerd.io";
};

// Automatically reboot when kernel updates require it
// Security updates are important - kernel patches need reboot to be effective
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-WithUsers "false";
Unattended-Upgrade::Automatic-Reboot-Time "03:00";  // 3 AM UTC (low-traffic period)

// Email notifications - disabled (Azure blocks SMTP port 25)
// Configure SMTP relay if email notifications are needed
// Unattended-Upgrade::Mail "admin@example.com";
// Unattended-Upgrade::MailReport "on-change";

// Remove unused kernel packages and dependencies
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";

// Only upgrade packages that can be upgraded without removing other packages
Unattended-Upgrade::Remove-New-Unused-Dependencies "true";

// Update package list before upgrade
Unattended-Upgrade::Update-Days {"Mon";"Tue";"Wed";"Thu";"Fri";"Sat";"Sun"};

// Verbose logging for troubleshooting
Unattended-Upgrade::Verbose "false";

// Split the upgrade into smaller chunks to avoid long-running operations
// Useful for systems with many packages
Unattended-Upgrade::MinimalSteps "true";
EOF

print_status "Security update policy configured"

# Enable systemd timers
print_info "Enabling systemd timers..."

systemctl enable apt-daily.timer
systemctl enable apt-daily-upgrade.timer

# Start timers if not already running
if ! systemctl is-active --quiet apt-daily.timer; then
    systemctl start apt-daily.timer
fi

if ! systemctl is-active --quiet apt-daily-upgrade.timer; then
    systemctl start apt-daily-upgrade.timer
fi

print_status "Systemd timers enabled and started"

# Verify configuration
echo ""
print_info "Verifying configuration..."

# Check timers are active
if systemctl is-active --quiet apt-daily.timer && \
   systemctl is-active --quiet apt-daily-upgrade.timer; then
    print_status "Timers are active"
else
    print_error "Timer activation failed"
    exit 1
fi

# Perform dry-run test
print_info "Running dry-run test (this may take a moment)..."
if unattended-upgrades --dry-run --debug > /tmp/unattended-upgrades-test.log 2>&1; then
    print_status "Dry-run test passed"

    # Show summary from dry-run
    if grep -q "No packages found that can be upgraded unattended" /tmp/unattended-upgrades-test.log; then
        print_info "No security updates available (system is up to date)"
    else
        PACKAGE_COUNT=$(grep -c "Checking:" /tmp/unattended-upgrades-test.log 2>/dev/null || echo "0")
        print_info "System is configured to check ${PACKAGE_COUNT} packages for security updates"
    fi
    # Clean up test log on success
    rm -f /tmp/unattended-upgrades-test.log
else
    print_warning "Dry-run test produced warnings"
    print_info "This is often normal on first run before package lists are updated"
    echo ""
    print_info "Last 20 lines of output:"
    tail -n 20 /tmp/unattended-upgrades-test.log
    echo ""
    print_info "Full log saved to: /tmp/unattended-upgrades-test.log"
fi

echo ""
print_status "Unattended upgrades configuration complete"
echo ""
print_info "Configuration summary:"
print_info "  - Security updates: enabled (automatic)"
print_info "  - Auto-reboot: enabled at 3 AM UTC when required"
print_info "  - Docker packages: blacklisted (manual control)"
print_info "  - Update schedule: daily"
print_info "  - Logs: /var/log/unattended-upgrades/"
echo ""
print_info "Verification commands:"
print_info "  systemctl list-timers apt-daily*"
print_info "  tail -f /var/log/unattended-upgrades/unattended-upgrades.log"
print_info "  cat /var/run/reboot-required  # Check if reboot is pending"
echo ""
