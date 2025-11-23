"""Tests for UFW Cloudflare IP configuration script."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

# Import the script module (need to add docker/scripts to path)
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "docker" / "scripts"))

from ufw_cloudflare import HttpxHTTPClient, UFWManager


class TestHttpxHTTPClient:
    """Tests for HttpxHTTPClient."""

    def test_fetch_success(self) -> None:
        """Test successful HTTP fetch."""
        with patch("ufw_cloudflare.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = "192.0.2.0/24\n198.51.100.0/24"
            mock_get.return_value = mock_response

            client = HttpxHTTPClient()
            result = client.fetch("https://example.com/ips")

            assert result == "192.0.2.0/24\n198.51.100.0/24"
            mock_get.assert_called_once_with("https://example.com/ips", timeout=30, follow_redirects=True)
            mock_response.raise_for_status.assert_called_once()

    def test_fetch_with_custom_timeout(self) -> None:
        """Test HTTP fetch with custom timeout."""
        with patch("ufw_cloudflare.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.text = "content"
            mock_get.return_value = mock_response

            client = HttpxHTTPClient()
            client.fetch("https://example.com/ips", timeout=60)

            mock_get.assert_called_once_with("https://example.com/ips", timeout=60, follow_redirects=True)

    def test_fetch_http_error(self) -> None:
        """Test HTTP fetch with error."""
        with patch("ufw_cloudflare.httpx.get") as mock_get:
            mock_get.side_effect = httpx.HTTPError("Connection failed")

            client = HttpxHTTPClient()
            with pytest.raises(httpx.HTTPError):
                client.fetch("https://example.com/ips")


class TestUFWManager:
    """Tests for UFWManager."""

    @pytest.fixture
    def mock_http_client(self) -> Mock:
        """Create a mock HTTP client."""
        return Mock()

    @pytest.fixture
    def manager(self, mock_http_client: Mock) -> UFWManager:
        """Create UFWManager with mock HTTP client."""
        return UFWManager(http_client=mock_http_client)

    def test_init_default_client(self) -> None:
        """Test UFWManager initializes with default HTTP client."""
        manager = UFWManager()
        assert isinstance(manager.http_client, HttpxHTTPClient)

    def test_init_custom_client(self, mock_http_client: Mock) -> None:
        """Test UFWManager initializes with custom HTTP client."""
        manager = UFWManager(http_client=mock_http_client)
        assert manager.http_client is mock_http_client

    def test_check_root_success(self, manager: UFWManager) -> None:
        """Test root check succeeds when running as root."""
        with patch("ufw_cloudflare.os.geteuid", return_value=0):
            manager.check_root()  # Should not raise

    def test_check_root_failure(self, manager: UFWManager) -> None:
        """Test root check fails when not running as root."""
        with (
            patch("ufw_cloudflare.os.geteuid", return_value=1000),
            pytest.raises(SystemExit) as exc_info,
        ):
            manager.check_root()

        assert exc_info.value.code == 1

    def test_run_command_success(self, manager: UFWManager) -> None:
        """Test running command successfully."""
        with patch("ufw_cloudflare.subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.stdout = "output"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = manager.run_command(["ufw", "status"])

            assert result.stdout == "output"
            mock_run.assert_called_once_with(
                ["ufw", "status"],
                check=True,
                capture_output=True,
                text=True,
            )

    def test_run_command_no_check(self, manager: UFWManager) -> None:
        """Test running command without check."""
        with patch("ufw_cloudflare.subprocess.run") as mock_run:
            manager.run_command(["ufw", "status"], check=False)

            mock_run.assert_called_once_with(
                ["ufw", "status"],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_run_command_validates_list_type(self, manager: UFWManager) -> None:
        """Test that run_command rejects non-list commands."""
        with pytest.raises(TypeError, match="cmd must be a list"):
            manager.run_command("ufw status")  # type: ignore # Testing runtime validation

    def test_fetch_cloudflare_ips_success(self, manager: UFWManager, mock_http_client: Mock) -> None:
        """Test fetching Cloudflare IPs successfully."""
        mock_http_client.fetch.side_effect = [
            "192.0.2.0/24\n198.51.100.0/24\n",
            "2001:db8::/32\n2001:db8:1::/48\n",
        ]

        ipv4, ipv6 = manager.fetch_cloudflare_ips()

        assert ipv4 == ["192.0.2.0/24", "198.51.100.0/24"]
        assert ipv6 == ["2001:db8::/32", "2001:db8:1::/48"]

        assert mock_http_client.fetch.call_count == 2
        mock_http_client.fetch.assert_any_call(manager.CF_IPS_V4_URL)
        mock_http_client.fetch.assert_any_call(manager.CF_IPS_V6_URL)

    def test_fetch_cloudflare_ips_http_error(self, manager: UFWManager, mock_http_client: Mock) -> None:
        """Test handling HTTP error when fetching IPs."""
        mock_http_client.fetch.side_effect = httpx.HTTPError("Network error")

        with pytest.raises(SystemExit) as exc_info:
            manager.fetch_cloudflare_ips()

        assert exc_info.value.code == 1

    def test_validate_ip_ranges_ipv4(self, manager: UFWManager) -> None:
        """Test validating IPv4 ranges."""
        content = "192.0.2.0/24\n198.51.100.0/24\n203.0.113.0/25\n"
        ranges = manager._validate_ip_ranges(content, family=4)

        assert ranges == ["192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/25"]

    def test_validate_ip_ranges_ipv6(self, manager: UFWManager) -> None:
        """Test validating IPv6 ranges."""
        content = "2001:db8::/32\n2001:db8:1::/48\n"
        ranges = manager._validate_ip_ranges(content, family=6)

        assert ranges == ["2001:db8::/32", "2001:db8:1::/48"]

    def test_validate_ip_ranges_with_whitespace(self, manager: UFWManager) -> None:
        """Test validating IP ranges with whitespace."""
        content = "  192.0.2.0/24  \n\n  198.51.100.0/24\n\n"
        ranges = manager._validate_ip_ranges(content, family=4)

        assert ranges == ["192.0.2.0/24", "198.51.100.0/24"]

    def test_validate_ip_ranges_wrong_family(self, manager: UFWManager) -> None:
        """Test validation fails when IP family doesn't match."""
        content = "2001:db8::/32\n"  # IPv6 in IPv4 validation

        with pytest.raises(SystemExit) as exc_info:
            manager._validate_ip_ranges(content, family=4)

        assert exc_info.value.code == 1

    def test_validate_ip_ranges_invalid_cidr(self, manager: UFWManager) -> None:
        """Test validation fails with invalid CIDR."""
        content = "192.0.2.0/24\ninvalid-ip\n198.51.100.0/24\n"

        with pytest.raises(SystemExit) as exc_info:
            manager._validate_ip_ranges(content, family=4)

        assert exc_info.value.code == 1

    def test_validate_ip_ranges_empty_content(self, manager: UFWManager) -> None:
        """Test validation fails with empty content."""
        content = "\n\n\n"

        with pytest.raises(SystemExit) as exc_info:
            manager._validate_ip_ranges(content, family=4)

        assert exc_info.value.code == 1

    def test_validate_ip_ranges_no_cidr_notation(self, manager: UFWManager) -> None:
        """Test validation accepts IP without CIDR notation (defaults to /32)."""
        content = "192.0.2.1\n"
        ranges = manager._validate_ip_ranges(content, family=4)

        assert ranges == ["192.0.2.1/32"]

    def test_reset_ufw(self, manager: UFWManager) -> None:
        """Test resetting UFW."""
        with patch.object(manager, "run_command") as mock_run:
            manager.reset_ufw()

            mock_run.assert_called_once_with(["ufw", "--force", "reset"])

    def test_set_default_policies(self, manager: UFWManager) -> None:
        """Test setting default UFW policies."""
        with patch.object(manager, "run_command") as mock_run:
            manager.set_default_policies()

            assert mock_run.call_count == 2
            mock_run.assert_any_call(["ufw", "default", "deny", "incoming"])
            mock_run.assert_any_call(["ufw", "default", "allow", "outgoing"])

    def test_configure_ssh_anywhere(self, manager: UFWManager) -> None:
        """Test configuring SSH access from anywhere."""
        with patch.object(manager, "run_command") as mock_run:
            manager.configure_ssh(ssh_from=None)

            mock_run.assert_called_once_with(["ufw", "allow", "22/tcp"])

    def test_configure_ssh_from_specific_ip(self, manager: UFWManager) -> None:
        """Test configuring SSH access from specific IP."""
        with patch.object(manager, "run_command") as mock_run:
            manager.configure_ssh(ssh_from="203.0.113.42")

            mock_run.assert_called_once_with(
                ["ufw", "allow", "from", "203.0.113.42", "to", "any", "port", "22", "proto", "tcp"]
            )

    def test_configure_ssh_from_cidr(self, manager: UFWManager) -> None:
        """Test configuring SSH access from CIDR range."""
        with patch.object(manager, "run_command") as mock_run:
            manager.configure_ssh(ssh_from="203.0.113.0/24")

            mock_run.assert_called_once_with(
                ["ufw", "allow", "from", "203.0.113.0/24", "to", "any", "port", "22", "proto", "tcp"]
            )

    def test_configure_ssh_invalid_ip(self, manager: UFWManager) -> None:
        """Test configuring SSH fails with invalid IP."""
        with pytest.raises(SystemExit) as exc_info:
            manager.configure_ssh(ssh_from="invalid-ip")

        assert exc_info.value.code == 1

    def test_delete_cloudflare_rules_no_existing_rules(self, manager: UFWManager) -> None:
        """Test deleting Cloudflare rules when none exist."""
        with patch.object(manager, "run_command") as mock_run:
            # Simulate UFW not configured
            mock_run.return_value = Mock(returncode=1, stdout="")

            manager.delete_cloudflare_rules()

            # Should only call ufw status, no delete commands
            mock_run.assert_called_once_with(["ufw", "status", "numbered"], check=False)

    def test_delete_cloudflare_rules_with_existing_rules(self, manager: UFWManager) -> None:
        """Test deleting existing Cloudflare rules for idempotency."""
        with patch.object(manager, "run_command") as mock_run:
            # Simulate UFW status with rules
            mock_run.return_value = Mock(
                returncode=0,
                stdout=(
                    "Status: active\n\n"
                    "To                         Action      From\n"
                    "--                         ------      ----\n"
                    "[ 1] 22/tcp                     ALLOW IN    Anywhere\n"
                    "[ 2] 80/tcp                     ALLOW IN    192.0.2.0/24\n"
                    "[ 3] 443/tcp                    ALLOW IN    192.0.2.0/24\n"
                    "[ 4] 80/tcp                     ALLOW IN    198.51.100.0/24\n"
                    "[ 5] 22/tcp (v6)                ALLOW IN    Anywhere (v6)\n"
                ),
            )

            manager.delete_cloudflare_rules()

            # Should delete rules 2, 3, 4 (80/443) in reverse order
            assert mock_run.call_count == 4  # 1 status + 3 deletes
            mock_run.assert_any_call(["ufw", "--force", "delete", "4"], check=False)
            mock_run.assert_any_call(["ufw", "--force", "delete", "3"], check=False)
            mock_run.assert_any_call(["ufw", "--force", "delete", "2"], check=False)

    def test_add_cloudflare_rules(self, manager: UFWManager) -> None:
        """Test adding Cloudflare IP rules."""
        with patch.object(manager, "run_command") as mock_run:
            ipv4_ranges = ["192.0.2.0/24", "198.51.100.0/24"]
            ipv6_ranges = ["2001:db8::/32"]

            manager.add_cloudflare_rules(ipv4_ranges, ipv6_ranges)

            # Should add 4 rules for IPv4 (2 IPs x 2 ports) + 2 for IPv6 = 6 total
            assert mock_run.call_count == 6

            # Check IPv4 rules
            mock_run.assert_any_call(
                ["ufw", "allow", "from", "192.0.2.0/24", "to", "any", "port", "80", "proto", "tcp"]
            )
            mock_run.assert_any_call(
                ["ufw", "allow", "from", "192.0.2.0/24", "to", "any", "port", "443", "proto", "tcp"]
            )
            mock_run.assert_any_call(
                ["ufw", "allow", "from", "198.51.100.0/24", "to", "any", "port", "80", "proto", "tcp"]
            )
            mock_run.assert_any_call(
                ["ufw", "allow", "from", "198.51.100.0/24", "to", "any", "port", "443", "proto", "tcp"]
            )

            # Check IPv6 rules
            mock_run.assert_any_call(
                ["ufw", "allow", "from", "2001:db8::/32", "to", "any", "port", "80", "proto", "tcp"]
            )
            mock_run.assert_any_call(
                ["ufw", "allow", "from", "2001:db8::/32", "to", "any", "port", "443", "proto", "tcp"]
            )

    def test_enable_ufw(self, manager: UFWManager) -> None:
        """Test enabling UFW."""
        with patch.object(manager, "run_command") as mock_run:
            manager.enable_ufw()

            mock_run.assert_called_once_with(["ufw", "--force", "enable"])

    def test_show_status(self, manager: UFWManager) -> None:
        """Test showing UFW status."""
        with patch.object(manager, "run_command") as mock_run:
            mock_run.return_value = Mock(
                stdout=(
                    "Status: active\n\n"
                    "To                         Action      From\n"
                    "--                         ------      ----\n"
                    + "\n".join([f"[{i:2}] Rule {i}" for i in range(1, 25)])
                ),
            )

            manager.show_status()

            mock_run.assert_called_once_with(["ufw", "status", "numbered"])

    def test_save_ip_ranges(self, manager: UFWManager) -> None:
        """Test saving IP ranges to files."""
        with patch("ufw_cloudflare.Path.write_text"):
            ipv4_ranges = ["192.0.2.0/24", "198.51.100.0/24"]
            ipv6_ranges = ["2001:db8::/32"]

            # Should not raise - just verifies the method runs without errors
            manager.save_ip_ranges(ipv4_ranges, ipv6_ranges)

    def test_save_ip_ranges_os_error(self, manager: UFWManager) -> None:
        """Test saving IP ranges handles OSError gracefully."""
        with patch("ufw_cloudflare.Path.write_text", side_effect=OSError("Permission denied")):
            # Should not raise - errors are non-fatal
            manager.save_ip_ranges(["192.0.2.0/24"], ["2001:db8::/32"])

    def test_configure_full_flow(self, manager: UFWManager, mock_http_client: Mock) -> None:
        """Test full configuration flow."""
        with (
            patch.object(manager, "check_root"),
            patch.object(manager, "fetch_cloudflare_ips") as mock_fetch,
            patch.object(manager, "reset_ufw") as mock_reset,
            patch.object(manager, "set_default_policies") as mock_policies,
            patch.object(manager, "configure_ssh") as mock_ssh,
            patch.object(manager, "delete_cloudflare_rules") as mock_delete,
            patch.object(manager, "add_cloudflare_rules") as mock_add,
            patch.object(manager, "enable_ufw") as mock_enable,
            patch.object(manager, "show_status") as mock_status,
            patch.object(manager, "save_ip_ranges") as mock_save,
        ):
            mock_fetch.return_value = (["192.0.2.0/24"], ["2001:db8::/32"])

            manager.configure(reset=True, ssh_from="203.0.113.42")

            # Verify all methods called in correct order
            mock_fetch.assert_called_once()
            mock_reset.assert_called_once()
            mock_policies.assert_called_once()
            mock_ssh.assert_called_once_with("203.0.113.42")
            mock_delete.assert_called_once()
            mock_add.assert_called_once_with(["192.0.2.0/24"], ["2001:db8::/32"])
            mock_enable.assert_called_once()
            mock_status.assert_called_once()
            mock_save.assert_called_once_with(["192.0.2.0/24"], ["2001:db8::/32"])

    def test_configure_without_reset(self, manager: UFWManager, mock_http_client: Mock) -> None:
        """Test configuration without reset."""
        with (
            patch.object(manager, "check_root"),
            patch.object(manager, "fetch_cloudflare_ips") as mock_fetch,
            patch.object(manager, "reset_ufw") as mock_reset,
            patch.object(manager, "set_default_policies"),
            patch.object(manager, "configure_ssh"),
            patch.object(manager, "delete_cloudflare_rules"),
            patch.object(manager, "add_cloudflare_rules"),
            patch.object(manager, "enable_ufw"),
            patch.object(manager, "show_status"),
            patch.object(manager, "save_ip_ranges"),
        ):
            mock_fetch.return_value = (["192.0.2.0/24"], ["2001:db8::/32"])

            manager.configure(reset=False, ssh_from=None)

            # Reset should not be called
            mock_reset.assert_not_called()


class TestMain:
    """Tests for main CLI function."""

    def test_main_default_args(self) -> None:
        """Test main with default arguments."""
        with (
            patch("sys.argv", ["ufw_cloudflare.py"]),
            patch("ufw_cloudflare.UFWManager") as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager_class.return_value = mock_manager

            from ufw_cloudflare import main  # noqa: PLC0415

            main()

            mock_manager_class.assert_called_once()
            mock_manager.configure.assert_called_once_with(reset=False, ssh_from=None)

    def test_main_with_reset(self) -> None:
        """Test main with --reset flag."""
        with (
            patch("sys.argv", ["ufw_cloudflare.py", "--reset"]),
            patch("ufw_cloudflare.UFWManager") as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager_class.return_value = mock_manager

            from ufw_cloudflare import main  # noqa: PLC0415

            main()

            mock_manager.configure.assert_called_once_with(reset=True, ssh_from=None)

    def test_main_with_ssh_from(self) -> None:
        """Test main with --ssh-from argument."""
        with (
            patch("sys.argv", ["ufw_cloudflare.py", "--ssh-from", "203.0.113.42"]),
            patch("ufw_cloudflare.UFWManager") as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager_class.return_value = mock_manager

            from ufw_cloudflare import main  # noqa: PLC0415

            main()

            mock_manager.configure.assert_called_once_with(reset=False, ssh_from="203.0.113.42")

    def test_main_with_all_args(self) -> None:
        """Test main with all arguments."""
        with (
            patch("sys.argv", ["ufw_cloudflare.py", "--reset", "--ssh-from", "203.0.113.0/24"]),
            patch("ufw_cloudflare.UFWManager") as mock_manager_class,
        ):
            mock_manager = Mock()
            mock_manager_class.return_value = mock_manager

            from ufw_cloudflare import main  # noqa: PLC0415

            main()

            mock_manager.configure.assert_called_once_with(reset=True, ssh_from="203.0.113.0/24")
