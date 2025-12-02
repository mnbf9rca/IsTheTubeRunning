#!/usr/bin/env bash
# Setup SSH deployment keys for CI/CD
# Generates/uses SSH keys and deploys public key to target VM

set -euo pipefail

# Source Azure configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./azure-config.sh
source "$SCRIPT_DIR/azure-config.sh"

# Declare required configuration for this script
validate_required_config \
    "AZURE_ADMIN_USERNAME" \
    "DEPLOYMENT_USER" \
    "AZURE_VM_NAME" \
    "AZURE_RESOURCE_GROUP" \
    "AZURE_SSH_KEY_NAME" || exit 1

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Parse command line arguments
KEY_FILE=""
ADMIN_KEY=""
GENERATE_NEW=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --key-file)
            KEY_FILE="$2"
            shift 2
            ;;
        --admin-key)
            ADMIN_KEY="$2"
            shift 2
            ;;
        --generate)
            GENERATE_NEW=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 --admin-key PATH (--key-file PATH | --generate)"
            echo ""
            echo "Required:"
            echo "  --admin-key PATH   Path to admin SSH private key (for azureuser access)"
            echo ""
            echo "Choose one:"
            echo "  --key-file PATH    Use existing deployment SSH key at PATH"
            echo "  --generate         Generate a new deployment SSH key"
            echo ""
            echo "Optional:"
            echo "  -h, --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 --admin-key ~/.ssh/id_rsa --generate"
            echo "  $0 --admin-key ~/.ssh/id_rsa --key-file ~/.ssh/deploy_key"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate --admin-key is provided
if [ -z "$ADMIN_KEY" ]; then
    print_error "--admin-key PATH is required"
    echo ""
    echo "Usage: $0 --admin-key PATH (--key-file PATH | --generate)"
    echo ""
    echo "Example:"
    echo "  $0 --admin-key ~/.ssh/id_rsa --generate"
    exit 1
fi

# Validate admin key exists
if [ ! -f "$ADMIN_KEY" ]; then
    print_error "Admin key file not found: $ADMIN_KEY"
    exit 1
fi

# Validate flags: require exactly one method, reject both
if [ -n "$KEY_FILE" ] && [ "$GENERATE_NEW" = true ]; then
    print_error "Cannot use both --key-file and --generate together"
    echo ""
    echo "Choose one method:"
    echo "  $0 --admin-key PATH --key-file PATH    # Use existing key"
    echo "  $0 --admin-key PATH --generate         # Generate new key"
    exit 1
fi

# Require explicit choice
if [ -z "$KEY_FILE" ] && [ "$GENERATE_NEW" = false ]; then
    print_error "Must specify either --key-file PATH or --generate"
    echo ""
    echo "Usage: $0 --admin-key PATH (--key-file PATH | --generate)"
    echo ""
    echo "Examples:"
    echo "  $0 --admin-key ~/.ssh/id_rsa --key-file ~/.ssh/deploy_key"
    echo "  $0 --admin-key ~/.ssh/id_rsa --generate"
    exit 1
fi

echo "========================================="
echo "  SSH Deployment Keys Setup"
echo "========================================="
echo ""

# Check prerequisites
print_info "Checking prerequisites..."

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    print_error "Azure CLI is not installed"
    echo ""
    echo "Install with: brew install azure-cli"
    exit 1
fi
print_status "Azure CLI found"

# Check if logged in to Azure
if ! az account show &> /dev/null; then
    print_error "Not logged in to Azure"
    echo ""
    echo "Login with: az login"
    exit 1
fi
print_status "Logged in to Azure"

# Get VM public IP dynamically
print_info "Retrieving VM public IP..."
VM_PUBLIC_IP=$(az vm list-ip-addresses \
    --name "$AZURE_VM_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --query "[0].virtualMachine.network.publicIpAddresses[0].ipAddress" \
    --output tsv)

if [ -z "$VM_PUBLIC_IP" ]; then
    print_error "Could not retrieve VM public IP"
    echo ""
    echo "Ensure VM '$AZURE_VM_NAME' exists in resource group '$AZURE_RESOURCE_GROUP'"
    exit 1
fi
print_status "VM public IP: $VM_PUBLIC_IP"

# Test SSH connectivity as admin user
print_info "Testing SSH connectivity as $AZURE_ADMIN_USERNAME..."
if ! ssh -i "$ADMIN_KEY" -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new \
    "${AZURE_ADMIN_USERNAME}@${VM_PUBLIC_IP}" "echo 'SSH test successful'" &>/dev/null; then
    print_error "Cannot connect to VM as $AZURE_ADMIN_USERNAME"
    echo ""
    echo "Check that:"
    echo "  1. VM is running"
    echo "  2. Admin key '$ADMIN_KEY' is authorized on the VM"
    echo "  3. Network allows SSH (port 22)"
    exit 1
fi
print_status "SSH connectivity verified"

echo ""

# Handle --generate flag
if [ "$GENERATE_NEW" = true ]; then
    # Default key file for generation
    if [ -z "$KEY_FILE" ]; then
        KEY_FILE="$HOME/.ssh/$AZURE_SSH_KEY_NAME"
    fi

    # Check if key already exists
    if [ -f "$KEY_FILE" ]; then
        print_error "Key already exists: $KEY_FILE"
        print_info "Delete it first or use --key-file to specify existing key"
        exit 1
    fi

    # Generate new key
    print_info "Generating ED25519 SSH key at: $KEY_FILE"
    mkdir -p "$(dirname "$KEY_FILE")"
    ssh-keygen -t ed25519 -f "$KEY_FILE" -C "github-actions-deploy" -N ""
    print_status "SSH key pair generated"
else
    # Using existing key
    if [ ! -f "$KEY_FILE" ]; then
        print_error "Key file not found: $KEY_FILE"
        exit 1
    fi

    if [ ! -f "${KEY_FILE}.pub" ]; then
        print_error "Public key not found: ${KEY_FILE}.pub"
        exit 1
    fi

    print_status "Using existing SSH key: $KEY_FILE"
fi

echo ""
echo "========================================="
echo "  Deploying Public Key to VM"
echo "========================================="
echo ""

PUBLIC_KEY=$(cat "${KEY_FILE}.pub")
print_info "Public key:"
echo "  $PUBLIC_KEY"
echo ""

# Deploy public key to VM (idempotent - checks if key already exists)
print_info "Deploying public key to $DEPLOYMENT_USER@$VM_PUBLIC_IP..."

# Extract key type and key data (first two fields) for idempotency check
KEY_FINGERPRINT=$(echo "$PUBLIC_KEY" | awk '{print $1, $2}')
AUTH_KEYS_FILE="/home/$DEPLOYMENT_USER/.ssh/authorized_keys"

# Check if key already exists on remote (idempotent)
if ssh -i "$ADMIN_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
    "${AZURE_ADMIN_USERNAME}@${VM_PUBLIC_IP}" \
    "sudo grep -qF \"$KEY_FINGERPRINT\" \"$AUTH_KEYS_FILE\" 2>/dev/null"; then
    print_status "Key already exists in authorized_keys (idempotent - no change needed)"
else
    # Create .ssh directory and add public key in single SSH call
    # Pipe PUBLIC_KEY through stdin to avoid shell escaping issues
    if echo "$PUBLIC_KEY" | ssh -i "$ADMIN_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
        "${AZURE_ADMIN_USERNAME}@${VM_PUBLIC_IP}" \
        "sudo mkdir -p \"/home/$DEPLOYMENT_USER/.ssh\" && \
         sudo chmod 700 \"/home/$DEPLOYMENT_USER/.ssh\" && \
         sudo chown \"$DEPLOYMENT_USER:$DEPLOYMENT_USER\" \"/home/$DEPLOYMENT_USER/.ssh\" && \
         sudo tee -a \"$AUTH_KEYS_FILE\" > /dev/null && \
         sudo chmod 600 \"$AUTH_KEYS_FILE\" && \
         sudo chown \"$DEPLOYMENT_USER:$DEPLOYMENT_USER\" \"$AUTH_KEYS_FILE\""; then
        print_status "Public key deployed to VM"
    else
        print_error "Failed to deploy public key to VM"
        exit 1
    fi
fi

echo ""
echo "========================================="
echo "  Testing Deployment SSH Connection"
echo "========================================="
echo ""

print_info "Testing SSH connection as $DEPLOYMENT_USER..."
if ssh -i "$KEY_FILE" -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new \
    "${DEPLOYMENT_USER}@${VM_PUBLIC_IP}" "echo 'Deployment SSH connection successful'"; then
    print_status "SSH connection as $DEPLOYMENT_USER verified"
else
    print_error "Failed to connect as $DEPLOYMENT_USER"
    echo ""
    echo "The public key was deployed but the connection test failed."
    echo "Check the key permissions and try manually:"
    echo "  ssh -i $KEY_FILE $DEPLOYMENT_USER@$VM_PUBLIC_IP"
    exit 1
fi

echo ""
echo "========================================="
echo "  Private Key (Add to GitHub Secrets)"
echo "========================================="
echo ""
print_warning "KEEP THIS PRIVATE! Add to GitHub Secrets as: DEPLOY_SSH_KEY"
echo ""
print_info "Private key location: $KEY_FILE"
print_warning "To view private key (be careful!): cat $KEY_FILE"
echo ""

echo "========================================="
echo "  GitHub Secrets to Configure"
echo "========================================="
echo ""
print_info "Add these secrets to your GitHub repository:"
echo ""
echo "  DEPLOY_SSH_KEY                  Private key content (cat $KEY_FILE)"
echo "  DEPLOY_HOST                     $VM_PUBLIC_IP"
echo "  DEPLOY_USER                     $DEPLOYMENT_USER"
echo "  DOTENV_PRIVATE_KEY_PRODUCTION   Production decryption key from .env.keys"
echo ""
print_info "To get DOTENV_PRIVATE_KEY_PRODUCTION:"
echo "  cd backend && grep DOTENV_PRIVATE_KEY_PRODUCTION .env.keys | cut -d'=' -f2-"
echo ""
print_warning "IMPORTANT: Never commit .env.keys to git (contains private decryption keys)"
echo ""

echo "========================================="
echo "  Summary"
echo "========================================="
echo ""
print_status "SSH deployment keys configured successfully!"
echo ""
echo "  VM Target:        $DEPLOYMENT_USER@$VM_PUBLIC_IP"
echo "  Private Key:      $KEY_FILE"
echo "  Public Key:       ${KEY_FILE}.pub"
echo ""
print_info "Next steps:"
echo "  1. Add private key to GitHub Secrets as DEPLOY_SSH_KEY"
echo "  2. Add VM IP ($VM_PUBLIC_IP) to GitHub Secrets as DEPLOY_HOST"
echo "  3. Configure remaining GitHub Secrets (see above)"
echo ""
