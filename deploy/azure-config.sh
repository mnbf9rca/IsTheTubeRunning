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

# Define required configuration keys
REQUIRED_CONFIG_KEYS=(
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

# Keys that are allowed to be empty (have auto-detection or other logic)
OPTIONAL_KEYS=(
    "AZURE_SSH_SOURCE_PREFIXES"  # Auto-detected in provision-azure-vm.sh
)

# Validate JSON syntax
if ! jq empty "$AZURE_CONFIG_FILE" 2>/dev/null; then
    echo "ERROR: Invalid JSON syntax in $AZURE_CONFIG_FILE" >&2
    return 1 2>/dev/null || exit 1
fi

# Check all required keys exist and have values
missing_keys=()
empty_keys=()

for key in "${REQUIRED_CONFIG_KEYS[@]}"; do
    # Check if key exists in JSON
    if ! jq -e "has(\"$key\")" "$AZURE_CONFIG_FILE" > /dev/null 2>&1; then
        missing_keys+=("$key")
        continue
    fi

    # Get value from JSON, allowing environment variable override
    value=$(jq -r ".$key" "$AZURE_CONFIG_FILE")

    # If environment variable is set, use it instead of JSON value
    if [[ -n "${!key:-}" ]]; then
        value="${!key}"
    fi

    # Check if value is empty (skip check for optional keys)
    if [[ -z "$value" && -z "${!key:-}" ]]; then
        # Check if this key is in the optional list
        is_optional=false
        for opt_key in "${OPTIONAL_KEYS[@]}"; do
            if [[ "$key" == "$opt_key" ]]; then
                is_optional=true
                break
            fi
        done
        if [[ "$is_optional" == false ]]; then
            empty_keys+=("$key")
        fi
    fi

    # Export the variable
    export "$key=$value"
done

# Report errors
if [[ ${#missing_keys[@]} -gt 0 || ${#empty_keys[@]} -gt 0 ]]; then
    echo "ERROR: Configuration validation failed" >&2
    echo "" >&2

    if [[ ${#missing_keys[@]} -gt 0 ]]; then
        echo "Missing keys in $AZURE_CONFIG_FILE:" >&2
        for key in "${missing_keys[@]}"; do
            echo "  - $key" >&2
        done
        echo "" >&2
    fi

    if [[ ${#empty_keys[@]} -gt 0 ]]; then
        echo "Empty values in $AZURE_CONFIG_FILE:" >&2
        for key in "${empty_keys[@]}"; do
            echo "  - $key" >&2
        done
        echo "" >&2

        # Special handling for AZURE_SUBSCRIPTION_ID
        if [[ " ${empty_keys[*]} " =~ " AZURE_SUBSCRIPTION_ID " ]]; then
            echo "AZURE_SUBSCRIPTION_ID is required. Set it by either:" >&2
            echo "  1. Environment variable: export AZURE_SUBSCRIPTION_ID=your-subscription-id" >&2
            echo "  2. Update azure-config.json with your subscription ID" >&2
            echo "" >&2
            echo "Find your subscription ID with:" >&2
            echo "  az account list --query '[].{name:name, id:id}' --output table" >&2
            echo "" >&2
        fi
    fi

    return 1 2>/dev/null || exit 1
fi
