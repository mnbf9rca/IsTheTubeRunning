#!/usr/bin/env bash
# Provision Azure VM for IsTheTubeRunning
# Creates all necessary Azure resources for production deployment

set -euo pipefail

# Source Azure configuration (validates automatically)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./azure-config.sh
source "$SCRIPT_DIR/azure-config.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Parse command line arguments
DRY_RUN=false
SSH_KEY_PATH=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --ssh-key)
            SSH_KEY_PATH="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 --ssh-key PATH [--dry-run]"
            echo ""
            echo "Required:"
            echo "  --ssh-key PATH    Path to existing SSH public key for VM admin access"
            echo ""
            echo "Optional:"
            echo "  --dry-run         Show what would be created without provisioning"
            echo "  -h, --help        Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate SSH key is provided and exists
if [ -z "$SSH_KEY_PATH" ]; then
    print_error "SSH key is required. Use --ssh-key PATH"
    echo ""
    echo "Example: $0 --ssh-key ~/.ssh/id_rsa.pub"
    exit 1
fi

if [ ! -f "$SSH_KEY_PATH" ]; then
    print_error "SSH key file not found: $SSH_KEY_PATH"
    exit 1
fi

print_status "Using SSH key: $SSH_KEY_PATH"

# Function to execute Azure CLI command with dry-run support
az_exec() {
    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] Would execute: az $*"
        return 0
    else
        az "$@"
    fi
}

echo "=== Azure VM Provisioning for IsTheTubeRunning ==="
echo ""
echo "Checking prerequisites..."
echo ""

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    print_error "Azure CLI is not installed"
    echo ""
    echo "Install with: brew install azure-cli"
    exit 1
fi
print_status "Azure CLI found"

# Check if logged in to Azure
if [ "$DRY_RUN" = false ]; then
    if ! az account show &> /dev/null; then
        print_error "Not logged in to Azure"
        echo ""
        echo "Login with: az login"
        exit 1
    fi
    print_status "Logged in to Azure"
fi

# Set subscription
echo ""
echo "Setting Azure subscription to: $AZURE_SUBSCRIPTION_ID"
az_exec account set --subscription "$AZURE_SUBSCRIPTION_ID"
print_status "Subscription set"

# Display configuration
echo ""
echo "Configuration:"
echo "  Subscription ID:   $AZURE_SUBSCRIPTION_ID"
echo "  Resource Group:    $AZURE_RESOURCE_GROUP"
echo "  Location:          $AZURE_LOCATION"
echo "  VM Name:           $AZURE_VM_NAME"
echo "  VM Size:           $AZURE_VM_SIZE"
echo "  OS Disk Size:      ${AZURE_VM_OS_DISK_SIZE}GB"
echo "  Storage Account:   $AZURE_STORAGE_ACCOUNT"
echo "  Admin Username:    $AZURE_ADMIN_USERNAME"
echo ""

if [ "$DRY_RUN" = true ]; then
    print_warning "DRY-RUN MODE: No actual resources will be created"
    echo ""
fi

read -p "Proceed with provisioning? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
    echo "Provisioning cancelled."
    exit 0
fi

echo ""
echo "=== Creating Azure Resources ==="
echo ""

# 1. Create Resource Group
echo "[1/11] Creating resource group..."
if az_exec group create \
    --name "$AZURE_RESOURCE_GROUP" \
    --location "$AZURE_LOCATION"; then
    print_status "Resource group '$AZURE_RESOURCE_GROUP' created/verified"
else
    print_error "Failed to create resource group"
    exit 1
fi

# 2. Create Virtual Network
echo "[2/11] Creating virtual network..."
if az_exec network vnet create \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$AZURE_VNET_NAME" \
    --address-prefix 10.0.0.0/16 \
    --subnet-name "$AZURE_SUBNET_NAME" \
    --subnet-prefix 10.0.1.0/24; then
    print_status "Virtual network '$AZURE_VNET_NAME' created"
else
    print_error "Failed to create virtual network"
    exit 1
fi

# 3. Create Network Security Group
echo "[3/11] Creating network security group..."
if az_exec network nsg create \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$AZURE_NSG_NAME"; then
    print_status "Network security group '$AZURE_NSG_NAME' created"
else
    print_error "Failed to create NSG"
    exit 1
fi

# Add NSG rules
# Auto-detect current IP for SSH access if not explicitly set
if [ -z "$AZURE_SSH_SOURCE_PREFIXES" ]; then
    print_status "Detecting current IP address for SSH access..."
    CURRENT_IP=$(curl -s -m 5 ifconfig.me || echo "")
    if [ -n "$CURRENT_IP" ]; then
        AZURE_SSH_SOURCE_PREFIXES="${CURRENT_IP}/32"
        print_status "Using current IP for SSH access: ${CURRENT_IP}/32"
        print_warning "To add more IPs later, modify the NSG rule via Azure Portal or set AZURE_SSH_SOURCE_PREFIXES env var"
    else
        print_error "Could not auto-detect current IP address"
        print_error "Set AZURE_SSH_SOURCE_PREFIXES environment variable (e.g., 'export AZURE_SSH_SOURCE_PREFIXES=\"203.0.113.0/24\"')"
        exit 1
    fi
fi

echo "    Adding SSH rule (port 22) for source: ${AZURE_SSH_SOURCE_PREFIXES}..."
az_exec network nsg rule create \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --nsg-name "$AZURE_NSG_NAME" \
    --name AllowSSH \
    --priority 1000 \
    --source-address-prefixes "$AZURE_SSH_SOURCE_PREFIXES" \
    --destination-port-ranges 22 \
    --access Allow \
    --protocol Tcp

# Note: NSG allows HTTP/HTTPS from any source (*) for Cloudflare connectivity.
# UFW firewall (configured by setup-vm.sh) restricts ports 80/443 to Cloudflare IP ranges only.
# This layered security approach allows Cloudflare to reach the VM while blocking direct access.
echo "    Adding HTTP rule (port 80)..."
az_exec network nsg rule create \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --nsg-name "$AZURE_NSG_NAME" \
    --name AllowHTTP \
    --priority 1001 \
    --source-address-prefixes '*' \
    --destination-port-ranges 80 \
    --access Allow \
    --protocol Tcp

echo "    Adding HTTPS rule (port 443)..."
az_exec network nsg rule create \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --nsg-name "$AZURE_NSG_NAME" \
    --name AllowHTTPS \
    --priority 1002 \
    --source-address-prefixes '*' \
    --destination-port-ranges 443 \
    --access Allow \
    --protocol Tcp

print_status "NSG rules configured"

# 4. Create Public IP
echo "[4/11] Creating public IP address..."
if az_exec network public-ip create \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$AZURE_PUBLIC_IP_NAME" \
    --sku Standard \
    --allocation-method Static; then
    print_status "Public IP '$AZURE_PUBLIC_IP_NAME' created"
else
    print_error "Failed to create public IP"
    exit 1
fi

# 5. Create Network Interface
echo "[5/11] Creating network interface..."
if az_exec network nic create \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "${AZURE_VM_NAME}-nic" \
    --vnet-name "$AZURE_VNET_NAME" \
    --subnet "$AZURE_SUBNET_NAME" \
    --network-security-group "$AZURE_NSG_NAME" \
    --public-ip-address "$AZURE_PUBLIC_IP_NAME"; then
    print_status "Network interface created"
else
    print_error "Failed to create network interface"
    exit 1
fi

# 6. Create Virtual Machine
echo "[6/11] Creating virtual machine (this may take a few minutes)..."
if az_exec vm create \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$AZURE_VM_NAME" \
    --nics "${AZURE_VM_NAME}-nic" \
    --size "$AZURE_VM_SIZE" \
    --image "$AZURE_VM_IMAGE" \
    --os-disk-size-gb "$AZURE_VM_OS_DISK_SIZE" \
    --admin-username "$AZURE_ADMIN_USERNAME" \
    --ssh-key-values "$SSH_KEY_PATH" \
    --assign-identity; then
    print_status "Virtual machine '$AZURE_VM_NAME' created"
else
    print_error "Failed to create virtual machine"
    exit 1
fi

# 7. Get Managed Identity Principal ID
echo "[7/11] Retrieving managed identity..."
if [ "$DRY_RUN" = false ]; then
    PRINCIPAL_ID=$(az vm identity show \
        --name "$AZURE_VM_NAME" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --query principalId \
        --output tsv)

    if [ -z "$PRINCIPAL_ID" ]; then
        print_error "Failed to retrieve managed identity principal ID"
        exit 1
    fi
    print_status "Managed identity retrieved: $PRINCIPAL_ID"
else
    PRINCIPAL_ID="dry-run-principal-id"
    print_status "Managed identity would be retrieved"
fi

# 8. Create Storage Account
echo "[8/11] Creating storage account..."
if az_exec storage account create \
    --name "$AZURE_STORAGE_ACCOUNT" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --location "$AZURE_LOCATION" \
    --sku Standard_LRS \
    --kind StorageV2 \
    --allow-blob-public-access false \
    --min-tls-version TLS1_2; then
    print_status "Storage account '$AZURE_STORAGE_ACCOUNT' created"
else
    print_error "Failed to create storage account"
    exit 1
fi

# 9. Create Blob Container
# Note: Requires 'Storage Blob Data Contributor' Azure RBAC role on the storage account.
# If this fails, assign the role: az role assignment create --assignee <user-email> \
#   --role "Storage Blob Data Contributor" --scope /subscriptions/.../storageAccounts/...
echo "[9/11] Creating blob container..."
if az_exec storage container create \
    --name "$AZURE_STORAGE_CONTAINER" \
    --account-name "$AZURE_STORAGE_ACCOUNT" \
    --auth-mode login; then
    print_status "Blob container '$AZURE_STORAGE_CONTAINER' created"
else
    print_error "Failed to create blob container"
    exit 1
fi

# 10. Configure Storage Lifecycle Management Policy
echo "[10/11] Configuring storage lifecycle policy (35-day retention)..."
POLICY_JSON=$(cat <<EOF
{
  "rules": [
    {
      "enabled": true,
      "name": "backup-retention-policy",
      "type": "Lifecycle",
      "definition": {
        "actions": {
          "baseBlob": {
            "delete": {
              "daysAfterModificationGreaterThan": 35
            }
          }
        },
        "filters": {
          "blobTypes": ["blockBlob"],
          "prefixMatch": ["backups/"]
        }
      }
    }
  ]
}
EOF
)

if [ "$DRY_RUN" = false ]; then
    echo "$POLICY_JSON" | az storage account management-policy create \
        --account-name "$AZURE_STORAGE_ACCOUNT" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --policy @-
    print_status "Lifecycle policy configured (35 day retention)"
else
    echo "[DRY-RUN] Would create lifecycle policy with 35 day retention"
fi

# 11. Assign Storage Role to Managed Identity
echo "[11/11] Assigning Storage Blob Data Contributor role..."
if [ "$DRY_RUN" = false ]; then
    STORAGE_ID=$(az storage account show \
        --name "$AZURE_STORAGE_ACCOUNT" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --query id \
        --output tsv)

    if az role assignment create \
        --assignee "$PRINCIPAL_ID" \
        --role "Storage Blob Data Contributor" \
        --scope "$STORAGE_ID"; then
        print_status "Role assigned to managed identity"
    else
        print_error "Failed to assign storage role"
        exit 1
    fi
else
    print_status "Role assignment would be created"
fi

# Get VM Public IP
echo ""
echo "=== Provisioning Complete ==="
echo ""

if [ "$DRY_RUN" = false ]; then
    VM_PUBLIC_IP=$(az network public-ip show \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --name "$AZURE_PUBLIC_IP_NAME" \
        --query ipAddress \
        --output tsv)

    print_status "VM is ready!"
    echo ""
    echo "VM Details:"
    echo "  Public IP:     $VM_PUBLIC_IP"
    echo "  SSH Command:   ssh ${AZURE_ADMIN_USERNAME}@${VM_PUBLIC_IP}"
    echo "  Resource Group: $AZURE_RESOURCE_GROUP"
    echo "  Location:      $AZURE_LOCATION"
    echo ""
    echo "Next steps:"
    echo "  1. Run setup-vm.sh to configure the VM"
    echo "  2. Run deploy-keys.sh to generate deployment SSH keys"
    echo ""
    echo "Save this IP address for later: $VM_PUBLIC_IP"
else
    echo "DRY-RUN completed successfully. No resources were created."
fi

echo ""
print_status "Provisioning script completed"
