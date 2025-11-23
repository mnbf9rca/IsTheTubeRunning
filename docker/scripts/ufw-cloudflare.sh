#!/usr/bin/env bash
# UFW Firewall configuration for Cloudflare IPs
# Configures firewall to allow only Cloudflare IPs on ports 80/443
#
# Prerequisites:
#   - UFW installed (apt install ufw)
#   - Root or sudo access
#   - curl installed
#
# Usage:
#   sudo ./ufw-cloudflare.sh [--reset] [--ssh-from IP]
#
# Options:
#   --reset         Reset UFW rules before applying new ones
#   --ssh-from IP   Allow SSH only from specific IP (default: allow from anywhere)
#
# Scheduling:
#   Add to cron for weekly updates:
#   0 2 * * 0 /path/to/ufw-cloudflare.sh >> /var/log/ufw-cloudflare.log 2>&1

set -euo pipefail

# Configuration
CF_IPS_V4_URL="https://www.cloudflare.com/ips-v4"
CF_IPS_V6_URL="https://www.cloudflare.com/ips-v6"
TMP_DIR="/tmp/cloudflare-ips"
RESET_UFW=false
SSH_FROM=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --reset)
            RESET_UFW=true
            shift
            ;;
        --ssh-from)
            SSH_FROM="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--reset] [--ssh-from IP]"
            exit 1
            ;;
    esac
done

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "ERROR: This script must be run as root (use sudo)"
   exit 1
fi

echo "=== UFW Cloudflare Configuration ==="
echo "Date: $(date)"
echo "Reset UFW: $RESET_UFW"
echo "SSH from: ${SSH_FROM:-anywhere}"
echo ""

# Create temp directory
mkdir -p "$TMP_DIR"

validate_cidr_file() {
    local file="$1"
    local family="$2"
    local pattern

    case "$family" in
        IPv4)
            # Basic IPv4 CIDR validation (e.g., 203.0.113.0/24)
            pattern='^([0-9]{1,3}\.){3}[0-9]{1,3}(/[0-9]{1,2})?$'
            ;;
        IPv6)
            # Basic IPv6 CIDR validation (e.g., 2400:cb00::/32)
            # This is intentionally lenient but rejects obvious non-IP content (like HTML)
            pattern='^[0-9a-fA-F:]+(/[0-9]{1,3})?$'
            ;;
        *)
            echo "ERROR: Unknown IP family '$family' for validation"
            exit 1
            ;;
    esac

    if [ ! -s "$file" ]; then
        echo "ERROR: $family ranges file '$file' is empty"
        exit 1
    fi

    # Fail if any non-empty line does NOT match the expected pattern
    if grep -Evq "$pattern" "$file"; then
        echo "ERROR: $family ranges file '$file' contains invalid entries"
        exit 1
    fi
}

# Fetch Cloudflare IP ranges
echo "Fetching Cloudflare IP ranges..."
if ! curl --silent --show-error --fail --connect-timeout 5 --max-time 30 \
    "$CF_IPS_V4_URL" -o "$TMP_DIR/cf-ips-v4.txt"; then
    echo "ERROR: Failed to fetch Cloudflare IPv4 ranges"
    exit 1
fi

if ! curl --silent --show-error --fail --connect-timeout 5 --max-time 30 \
    "$CF_IPS_V6_URL" -o "$TMP_DIR/cf-ips-v6.txt"; then
    echo "ERROR: Failed to fetch Cloudflare IPv6 ranges"
    exit 1
fi

# Remove blank lines (if any) before validation
sed -i.bak '/^[[:space:]]*$/d' "$TMP_DIR/cf-ips-v4.txt" "$TMP_DIR/cf-ips-v6.txt"

# Validate that each line is a plausible IP/CIDR, to avoid e.g. HTML error pages
validate_cidr_file "$TMP_DIR/cf-ips-v4.txt" "IPv4"
validate_cidr_file "$TMP_DIR/cf-ips-v6.txt" "IPv6"

IPV4_COUNT=$(wc -l < "$TMP_DIR/cf-ips-v4.txt")
IPV6_COUNT=$(wc -l < "$TMP_DIR/cf-ips-v6.txt")
echo "✓ Fetched $IPV4_COUNT IPv4 ranges and $IPV6_COUNT IPv6 ranges"
echo ""

# Reset UFW if requested
if [[ "$RESET_UFW" == true ]]; then
    echo "Resetting UFW rules..."
    ufw --force reset
    echo "✓ UFW reset complete"
    echo ""
fi

# Set default policies
echo "Setting default UFW policies..."
ufw default deny incoming
ufw default allow outgoing
echo "✓ Default policies set (deny incoming, allow outgoing)"
echo ""

# Allow SSH
echo "Configuring SSH access..."
if [[ -n "$SSH_FROM" ]]; then
    ufw allow from "$SSH_FROM" to any port 22 proto tcp
    echo "✓ SSH allowed from $SSH_FROM"
else
    ufw allow 22/tcp
    echo "✓ SSH allowed from anywhere"
fi
echo ""

# Allow Cloudflare IPs on ports 80 and 443
echo "Configuring Cloudflare IP access (ports 80/443)..."

# IPv4 ranges
while IFS= read -r ip; do
    [[ -z "$ip" ]] && continue
    ufw allow from "$ip" to any port 80 proto tcp
    ufw allow from "$ip" to any port 443 proto tcp
done < "$TMP_DIR/cf-ips-v4.txt"

# IPv6 ranges
while IFS= read -r ip; do
    [[ -z "$ip" ]] && continue
    ufw allow from "$ip" to any port 80 proto tcp
    ufw allow from "$ip" to any port 443 proto tcp
done < "$TMP_DIR/cf-ips-v6.txt"

echo "✓ Cloudflare IP rules added ($IPV4_COUNT IPv4 + $IPV6_COUNT IPv6 ranges)"
echo ""

# Enable UFW
echo "Enabling UFW..."
ufw --force enable
echo "✓ UFW enabled"
echo ""

# Show status
echo "=== UFW Status ==="
ufw status numbered | head -20
echo ""
echo "Total rules: $(ufw status numbered | grep -c '^\[')"
echo ""

# Save IP ranges for future comparison (change detection)
cp "$TMP_DIR/cf-ips-v4.txt" "/var/lib/cloudflare-ips-v4.txt" 2>/dev/null || true
cp "$TMP_DIR/cf-ips-v6.txt" "/var/lib/cloudflare-ips-v6.txt" 2>/dev/null || true

# Cleanup
rm -rf "$TMP_DIR"

echo "=== Configuration Complete ==="
echo ""
echo "To schedule weekly updates, add to crontab:"
echo "  0 2 * * 0 $0 >> /var/log/ufw-cloudflare.log 2>&1"
echo ""
echo "To view current rules: sudo ufw status numbered"
echo "To reset and reconfigure: sudo $0 --reset"
