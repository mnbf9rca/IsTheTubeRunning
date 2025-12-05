#!/bin/bash
# Get the public IP address of the production VM using Azure CLI
# This script can be used both locally and in CI/CD pipelines
# Configuration is loaded from deploy/azure-config.json

set -euo pipefail

# Get script directory and repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      echo "Usage: $0 [options]"
      echo ""
      echo "Get the public IP address of the production Azure VM"
      echo "Configuration is loaded from deploy/azure-config.json"
      echo ""
      echo "Options:"
      echo "  -h, --help           Show this help message"
      echo ""
      echo "Environment variables (override config file):"
      echo "  AZURE_RESOURCE_GROUP  Azure resource group"
      echo "  AZURE_VM_NAME         Azure VM name"
      exit 0
      ;;
    *)
      echo "Error: Unknown option $1" >&2
      echo "Run '$0 --help' for usage information" >&2
      exit 1
      ;;
  esac
done

# Load Azure configuration from deploy/azure-config.sh
# shellcheck source=../deploy/azure-config.sh
if [[ -f "$REPO_ROOT/deploy/azure-config.sh" ]]; then
  source "$REPO_ROOT/deploy/azure-config.sh"
else
  echo "Error: Could not find deploy/azure-config.sh" >&2
  exit 1
fi

# Check if az CLI is installed
if ! command -v az > /dev/null 2>&1; then
  echo "Error: Azure CLI (az) is not installed" >&2
  echo "Install from: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli" >&2
  exit 1
fi

# Check if user is logged in to Azure (show error output for debugging)
if ! az account show > /dev/null; then
  echo "Error: Not logged in to Azure CLI or authentication failed" >&2
  echo "Run 'az login' to authenticate" >&2
  exit 1
fi

# Get the VM IP address
VM_IP=$(az vm list-ip-addresses \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_VM_NAME" \
  --query '[0].virtualMachine.network.publicIpAddresses[0].ipAddress' \
  --output tsv)

# Validate the result
if [ -z "$VM_IP" ] || [ "$VM_IP" = "null" ]; then
  echo "Error: Could not retrieve IP address for VM '$AZURE_VM_NAME' in resource group '$AZURE_RESOURCE_GROUP'" >&2
  exit 1
fi

# Output the IP address (this can be captured by callers)
echo "$VM_IP"
