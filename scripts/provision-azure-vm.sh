#!/usr/bin/env bash
# Provision Azure VM for IsTheTubeRunning
# This is a STUB script - full implementation will be in Issue #241

set -euo pipefail

# Source Azure configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./azure-config.sh
source "$SCRIPT_DIR/azure-config.sh"

echo "=== Azure VM Provisioning (STUB - Issue #241) ==="
echo ""
echo "This script will provision Azure infrastructure:"
echo "  - Resource Group: $AZURE_RESOURCE_GROUP"
echo "  - Location: $AZURE_LOCATION"
echo "  - VM Name: $AZURE_VM_NAME"
echo "  - VM Size: $AZURE_VM_SIZE"
echo "  - OS Disk: ${AZURE_VM_OS_DISK_SIZE}GB"
echo "  - Image: $AZURE_VM_IMAGE"
echo ""
echo "Full implementation tasks (Issue #241):"
echo "  1. Create resource group (if not exists)"
echo "  2. Create virtual network and subnet"
echo "  3. Create network security group"
echo "  4. Create public IP address"
echo "  5. Create network interface"
echo "  6. Create virtual machine"
echo "  7. Enable system-assigned managed identity"
echo "  8. Create storage account for backups"
echo "  9. Assign Storage Blob Data Contributor role to managed identity"
echo " 10. Output VM public IP and SSH connection string"
echo ""
echo "Example commands that will be implemented:"
echo "  az group create --name $AZURE_RESOURCE_GROUP --location $AZURE_LOCATION"
echo "  az vm create --resource-group $AZURE_RESOURCE_GROUP --name $AZURE_VM_NAME \\"
echo "    --size $AZURE_VM_SIZE --image $AZURE_VM_IMAGE \\"
echo "    --admin-username $AZURE_ADMIN_USERNAME --generate-ssh-keys \\"
echo "    --assign-identity --os-disk-size-gb $AZURE_VM_OS_DISK_SIZE"
echo ""
echo "NOTE: This is a stub. Actual provisioning will be implemented in Issue #241."
