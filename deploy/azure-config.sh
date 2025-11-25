#!/usr/bin/env bash
# Azure Configuration Loader
# Parses azure-config.json and exports environment variables
# Usage: source "$(dirname "$0")/azure-config.sh"

# shellcheck disable=SC2317  # return/exit pattern is intentional for sourced scripts
set -euo pipefail

# Get script directory
AZURE_CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AZURE_CONFIG_FILE="$AZURE_CONFIG_DIR/azure-config.json"

# Check if config file exists
if [[ ! -f "$AZURE_CONFIG_FILE" ]]; then
    echo "ERROR: Configuration file not found: $AZURE_CONFIG_FILE" >&2
    return 1 2>/dev/null || exit 1
fi

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo "ERROR: jq is required to parse azure-config.json" >&2
    echo "Install with: apt-get install -y jq" >&2
    return 1 2>/dev/null || exit 1
fi

# All configuration keys available in azure-config.json
ALL_CONFIG_KEYS=(
    "AZURE_SUBSCRIPTION_ID"
    "AZURE_RESOURCE_GROUP"
    "AZURE_LOCATION"
    "AZURE_VM_NAME"
    "AZURE_VM_SIZE"
    "AZURE_VM_IMAGE"
    "AZURE_VM_OS_DISK_SIZE"
    "AZURE_ADMIN_USERNAME"
    "AZURE_VNET_NAME"
    "AZURE_SUBNET_NAME"
    "AZURE_NSG_NAME"
    "AZURE_PUBLIC_IP_NAME"
    "AZURE_SSH_SOURCE_PREFIXES"
    "AZURE_STORAGE_ACCOUNT"
    "AZURE_STORAGE_CONTAINER"
    "AZURE_SSH_KEY_NAME"
    "DEPLOYMENT_USER"
    "APP_DIR"
    "DOMAIN_NAME"
)

# Validate JSON syntax
if ! jq empty "$AZURE_CONFIG_FILE" 2>/dev/null; then
    echo "ERROR: Invalid JSON syntax in $AZURE_CONFIG_FILE" >&2
    return 1 2>/dev/null || exit 1
fi

# Load all configuration keys from JSON and export as variables
for key in "${ALL_CONFIG_KEYS[@]}"; do
    # Check if key exists in JSON
    if ! jq -e "has(\"$key\")" "$AZURE_CONFIG_FILE" > /dev/null 2>&1; then
        echo "ERROR: Missing key in $AZURE_CONFIG_FILE: $key" >&2
        return 1 2>/dev/null || exit 1
    fi

    # Get value from JSON, allowing environment variable override
    value=$(jq -r ".$key" "$AZURE_CONFIG_FILE")

    # If environment variable is set, use it instead of JSON value
    if [[ -n "${!key:-}" ]]; then
        value="${!key}"
    fi

    # Export the variable
    export "$key=$value"
done

# Validation function for scripts to declare their required variables
# Usage: validate_required_config "VAR1" "VAR2" "VAR3"
validate_required_config() {
    local required_vars=("$@")
    local missing_vars=()

    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            missing_vars+=("$var")
        fi
    done

    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        echo "ERROR: Missing required configuration for this script:" >&2
        for var in "${missing_vars[@]}"; do
            echo "  - $var" >&2
        done
        echo "" >&2

        # Special handling for AZURE_SUBSCRIPTION_ID
        if [[ " ${missing_vars[*]} " =~ " AZURE_SUBSCRIPTION_ID " ]]; then
            echo "Set AZURE_SUBSCRIPTION_ID by either:" >&2
            echo "  1. Environment variable: export AZURE_SUBSCRIPTION_ID=your-subscription-id" >&2
            echo "  2. Update deploy/azure-config.json" >&2
            echo "" >&2
            echo "Find your subscription ID:" >&2
            echo "  az account list --query '[].{name:name, id:id}' --output table" >&2
            echo "" >&2
        fi

        return 1
    fi

    return 0
}
