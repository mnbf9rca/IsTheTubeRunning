#!/usr/bin/env python3
"""UFW Firewall configuration for Cloudflare IPs.

Configures firewall to allow only Cloudflare IPs on ports 80/443.

Prerequisites:
    - UFW installed (apt install ufw)
    - Root or sudo access
    - requests library (pip install requests)

Usage:
    sudo ./ufw_cloudflare.py [--reset] [--ssh-from IP]

Options:
    --reset         Reset UFW rules before applying new ones
    --ssh-from IP   Allow SSH only from specific IP (default: allow from anywhere)

Scheduling:
    Add to cron for weekly updates:
    0 2 * * 0 /path/to/ufw_cloudflare.py >> /var/log/ufw-cloudflare.log 2>&1

The script is idempotent - running it multiple times will maintain the same
firewall state without creating duplicate rules.
"""

import argparse
import ipaddress
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Protocol

import httpx


class HTTPClient(Protocol):
    """Protocol for HTTP clients to enable testing."""

    def fetch(self, url: str) -> str:
        """Fetch content from URL."""
        ...


class HttpxHTTPClient:
    """HTTP client using httpx."""

    def fetch(self, url: str, timeout: int = 30) -> str:
        """Fetch content from URL with timeout.

        Args:
            url: URL to fetch
            timeout: Request timeout in seconds

        Returns:
            Response content as string

        Raises:
            httpx.HTTPError: If request fails
        """
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        return response.text


class UFWManager:
    """Manages UFW firewall rules for Cloudflare IPs."""

    # Cloudflare IP range URLs
    CF_IPS_V4_URL = "https://www.cloudflare.com/ips-v4"
    CF_IPS_V6_URL = "https://www.cloudflare.com/ips-v6"

    # UFW rule comment marker for idempotency
    RULE_COMMENT = "cloudflare-managed"

    def __init__(self, http_client: HTTPClient | None = None) -> None:
        """Initialize UFW manager.

        Args:
            http_client: HTTP client for fetching IP ranges (defaults to HttpxHTTPClient)
        """
        self.http_client = http_client or HttpxHTTPClient()

    def check_root(self) -> None:
        """Check if running as root, exit if not."""
        if os.geteuid() != 0:
            print("ERROR: This script must be run as root (use sudo)", file=sys.stderr)
            sys.exit(1)

    def run_command(self, cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        """Run a shell command and return result.

        Args:
            cmd: Command and arguments as list
            check: Raise exception on non-zero exit code

        Returns:
            CompletedProcess with stdout/stderr

        Security:
            Uses list-based arguments (not shell=True) to prevent command injection.
            All UFW commands are constructed with known-safe literal strings and
            validated IP addresses (via ipaddress module).
        """
        # Validate cmd is a list to prevent accidental shell injection
        if not isinstance(cmd, list):
            raise TypeError(f"cmd must be a list, got {type(cmd)}")

        # Safe: cmd is a list, shell=False (default), all arguments are properly escaped by Python
        return subprocess.run(  # noqa: S603 # Using list prevents shell injection
            cmd,
            check=check,
            capture_output=True,
            text=True,
        )

    def fetch_cloudflare_ips(self) -> tuple[list[str], list[str]]:
        """Fetch and validate Cloudflare IP ranges.

        Returns:
            Tuple of (ipv4_ranges, ipv6_ranges) as lists of CIDR strings

        Raises:
            SystemExit: If fetching or validation fails
        """
        print("Fetching Cloudflare IP ranges...")

        try:
            ipv4_content = self.http_client.fetch(self.CF_IPS_V4_URL)
            ipv6_content = self.http_client.fetch(self.CF_IPS_V6_URL)
        except httpx.HTTPError as e:
            print(f"ERROR: Failed to fetch Cloudflare IP ranges: {e}", file=sys.stderr)
            sys.exit(1)

        # Parse and validate IP ranges
        ipv4_ranges = self._validate_ip_ranges(ipv4_content, family=4)
        ipv6_ranges = self._validate_ip_ranges(ipv6_content, family=6)

        print(f"✓ Fetched {len(ipv4_ranges)} IPv4 ranges and {len(ipv6_ranges)} IPv6 ranges")
        print()

        return ipv4_ranges, ipv6_ranges

    def _validate_ip_ranges(self, content: str, family: int) -> list[str]:
        """Validate IP ranges from content string.

        Args:
            content: Newline-separated IP ranges
            family: IP family (4 or 6)

        Returns:
            List of validated CIDR strings

        Raises:
            SystemExit: If validation fails
        """
        ranges = []
        family_name = f"IPv{family}"

        for line_num, line in enumerate(content.strip().split("\n"), start=1):
            line = line.strip()
            if not line:  # Skip empty lines
                continue

            try:
                # Use ipaddress module for robust validation
                network = ipaddress.ip_network(line, strict=False)
                if network.version != family:
                    print(
                        f"ERROR: {family_name} file contains wrong IP version "
                        f"at line {line_num}: {line}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                ranges.append(str(network))
            except ValueError as e:
                print(
                    f"ERROR: {family_name} file contains invalid CIDR at line {line_num}: "
                    f"{line} ({e})",
                    file=sys.stderr,
                )
                sys.exit(1)

        if not ranges:
            print(f"ERROR: No valid {family_name} ranges found", file=sys.stderr)
            sys.exit(1)

        return ranges

    def reset_ufw(self) -> None:
        """Reset UFW to default state."""
        print("Resetting UFW rules...")
        self.run_command(["ufw", "--force", "reset"])
        print("✓ UFW reset complete")
        print()

    def set_default_policies(self) -> None:
        """Set UFW default policies (deny incoming, allow outgoing)."""
        print("Setting default UFW policies...")
        self.run_command(["ufw", "default", "deny", "incoming"])
        self.run_command(["ufw", "default", "allow", "outgoing"])
        print("✓ Default policies set (deny incoming, allow outgoing)")
        print()

    def configure_ssh(self, ssh_from: str | None = None) -> None:
        """Configure SSH access.

        Args:
            ssh_from: Restrict SSH to this IP/CIDR, or None for anywhere
        """
        print("Configuring SSH access...")

        if ssh_from:
            # Validate the SSH source IP
            try:
                ipaddress.ip_network(ssh_from, strict=False)
            except ValueError as e:
                print(f"ERROR: Invalid SSH source IP/CIDR: {ssh_from} ({e})", file=sys.stderr)
                sys.exit(1)

            self.run_command([
                "ufw", "allow", "from", ssh_from,
                "to", "any", "port", "22", "proto", "tcp"
            ])
            print(f"✓ SSH allowed from {ssh_from}")
        else:
            self.run_command(["ufw", "allow", "22/tcp"])
            print("✓ SSH allowed from anywhere")

        print()

    def delete_cloudflare_rules(self) -> None:
        """Delete existing Cloudflare rules (for idempotency).

        This ensures running the script multiple times doesn't create
        duplicate rules.
        """
        # Get all UFW rules
        result = self.run_command(["ufw", "status", "numbered"], check=False)
        if result.returncode != 0:
            return  # UFW not configured yet

        # Parse rules and find ones with our comment marker
        # UFW numbered output format: "[ 1] rule_text"
        # Note: We can't easily check comments via CLI, so we'll delete
        # all rules for ports 80/443 that aren't SSH before re-adding
        # This is safe because we control all 80/443 rules

        # For idempotency, we'll use a different approach:
        # 1. Check if rules exist for Cloudflare IPs
        # 2. If they do, delete them all before adding new ones
        # This is simpler and more reliable than comment parsing

        # Get raw status to check for port 80/443 rules
        lines = result.stdout.strip().split("\n")
        rules_to_delete = []

        for line in lines:
            # Skip headers and empty lines
            if not line.strip() or not line.startswith("["):
                continue

            # Check if rule is for port 80 or 443 (not SSH)
            if ("80" in line or "443" in line) and "22" not in line:
                # Extract rule number
                try:
                    rule_num = line.split("]")[0].strip("[").strip()
                    rules_to_delete.append(int(rule_num))
                except (ValueError, IndexError):
                    continue

        # Delete rules in reverse order to avoid renumbering issues
        if rules_to_delete:
            print(f"Removing {len(rules_to_delete)} existing Cloudflare rules for idempotency...")
            for rule_num in sorted(rules_to_delete, reverse=True):
                self.run_command(["ufw", "--force", "delete", str(rule_num)], check=False)
            print("✓ Existing Cloudflare rules removed")
            print()

    def add_cloudflare_rules(self, ipv4_ranges: list[str], ipv6_ranges: list[str]) -> None:
        """Add UFW rules for Cloudflare IP ranges on ports 80/443.

        Args:
            ipv4_ranges: List of IPv4 CIDR ranges
            ipv6_ranges: List of IPv6 CIDR ranges
        """
        print("Configuring Cloudflare IP access (ports 80/443)...")

        # Add IPv4 rules
        for ip_range in ipv4_ranges:
            for port in ["80", "443"]:
                self.run_command([
                    "ufw", "allow", "from", ip_range,
                    "to", "any", "port", port, "proto", "tcp"
                ])

        # Add IPv6 rules
        for ip_range in ipv6_ranges:
            for port in ["80", "443"]:
                self.run_command([
                    "ufw", "allow", "from", ip_range,
                    "to", "any", "port", port, "proto", "tcp"
                ])

        total_rules = (len(ipv4_ranges) + len(ipv6_ranges)) * 2
        print(
            f"✓ Cloudflare IP rules added "
            f"({len(ipv4_ranges)} IPv4 + {len(ipv6_ranges)} IPv6 ranges, "
            f"{total_rules} total rules)"
        )
        print()

    def enable_ufw(self) -> None:
        """Enable UFW firewall."""
        print("Enabling UFW...")
        self.run_command(["ufw", "--force", "enable"])
        print("✓ UFW enabled")
        print()

    def show_status(self) -> None:
        """Show UFW status and rule count."""
        print("=== UFW Status ===")
        result = self.run_command(["ufw", "status", "numbered"])

        # Show first 20 lines
        lines = result.stdout.strip().split("\n")
        for line in lines[:20]:
            print(line)

        if len(lines) > 20:
            print(f"... ({len(lines) - 20} more lines)")

        print()

        # Count rules (lines starting with '[')
        rule_count = sum(1 for line in lines if line.strip().startswith("["))
        print(f"Total rules: {rule_count}")
        print()

    def save_ip_ranges(self, ipv4_ranges: list[str], ipv6_ranges: list[str]) -> None:
        """Save IP ranges for future comparison (change detection).

        Args:
            ipv4_ranges: List of IPv4 CIDR ranges
            ipv6_ranges: List of IPv6 CIDR ranges
        """
        try:
            Path("/var/lib/cloudflare-ips-v4.txt").write_text("\n".join(ipv4_ranges) + "\n")
            Path("/var/lib/cloudflare-ips-v6.txt").write_text("\n".join(ipv6_ranges) + "\n")
        except OSError:
            # Non-fatal - just for change detection
            pass

    def configure(self, reset: bool = False, ssh_from: str | None = None) -> None:
        """Run full UFW configuration.

        Args:
            reset: Reset UFW rules before configuring
            ssh_from: Restrict SSH to this IP/CIDR, or None for anywhere
        """
        print("=== UFW Cloudflare Configuration ===")
        print(f"Date: {datetime.now()}")
        print(f"Reset UFW: {reset}")
        print(f"SSH from: {ssh_from or 'anywhere'}")
        print()

        self.check_root()

        # Fetch and validate IP ranges
        ipv4_ranges, ipv6_ranges = self.fetch_cloudflare_ips()

        # Reset if requested
        if reset:
            self.reset_ufw()

        # Set default policies
        self.set_default_policies()

        # Configure SSH
        self.configure_ssh(ssh_from)

        # Delete existing Cloudflare rules for idempotency
        self.delete_cloudflare_rules()

        # Add new Cloudflare rules
        self.add_cloudflare_rules(ipv4_ranges, ipv6_ranges)

        # Enable UFW
        self.enable_ufw()

        # Show status
        self.show_status()

        # Save IP ranges
        self.save_ip_ranges(ipv4_ranges, ipv6_ranges)

        # Success message
        print("=== Configuration Complete ===")
        print()
        print("To schedule weekly updates, add to crontab:")
        print(f"  0 2 * * 0 {os.path.abspath(__file__)} >> /var/log/ufw-cloudflare.log 2>&1")
        print()
        print("To view current rules: sudo ufw status numbered")
        print(f"To reset and reconfigure: sudo {os.path.abspath(__file__)} --reset")
        print()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Configure UFW firewall for Cloudflare IPs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initial setup
  sudo ./ufw_cloudflare.py

  # Reset and reconfigure
  sudo ./ufw_cloudflare.py --reset

  # Restrict SSH to specific IP
  sudo ./ufw_cloudflare.py --ssh-from 203.0.113.42
        """,
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset UFW rules before applying new ones",
    )
    parser.add_argument(
        "--ssh-from",
        metavar="IP",
        help="Allow SSH only from specific IP/CIDR (default: anywhere)",
    )

    args = parser.parse_args()

    manager = UFWManager()
    manager.configure(reset=args.reset, ssh_from=args.ssh_from)


if __name__ == "__main__":
    main()
