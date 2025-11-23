#!/usr/bin/env bash
# Setup SSH deployment keys for CI/CD
# Use existing keys or generate new ones

set -euo pipefail

# Source Azure configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./azure-config.sh
source "$SCRIPT_DIR/azure-config.sh"

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
GENERATE_NEW=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --key-file)
            KEY_FILE="$2"
            shift 2
            ;;
        --generate)
            GENERATE_NEW=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--key-file PATH] [--generate]"
            echo ""
            echo "Options:"
            echo "  --key-file PATH    Use existing SSH key at PATH"
            echo "  --generate         Generate a new SSH key"
            echo "  -h, --help         Show this help message"
            echo ""
            echo "If no options provided, will use default key or prompt to generate"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "========================================="
echo "  SSH Deployment Keys Setup"
echo "========================================="
echo ""

# Default key file if not specified
if [ -z "$KEY_FILE" ]; then
    KEY_FILE="$HOME/.ssh/$AZURE_SSH_KEY_NAME"
fi

# Check if key exists
if [ -f "$KEY_FILE" ]; then
    print_status "Found existing SSH key: $KEY_FILE"

    if [ "$GENERATE_NEW" = true ]; then
        print_warning "--generate flag set but key already exists"
        read -p "Overwrite existing key? (yes/no): " -r
        if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
            print_info "Using existing key"
        else
            print_info "Removing existing key..."
            rm -f "$KEY_FILE" "${KEY_FILE}.pub"
            GENERATE_NEW=true
        fi
    fi
else
    print_info "No existing key found at: $KEY_FILE"

    if [ "$GENERATE_NEW" = false ]; then
        read -p "Generate new SSH key? (yes/no): " -r
        if [[ $REPLY =~ ^[Yy]es$ ]]; then
            GENERATE_NEW=true
        else
            print_error "No key file specified and generation declined"
            echo ""
            print_info "Usage: $0 --key-file /path/to/existing/key"
            print_info "   or: $0 --generate"
            exit 1
        fi
    fi
fi

# Generate SSH key pair if needed
if [ "$GENERATE_NEW" = true ] && [ ! -f "$KEY_FILE" ]; then
    print_info "Generating ED25519 SSH key pair..."

    # Create directory if it doesn't exist
    mkdir -p "$(dirname "$KEY_FILE")"

    ssh-keygen -t ed25519 -f "$KEY_FILE" -C "github-actions-deploy" -N ""
    print_status "SSH key pair generated"
elif [ -f "$KEY_FILE" ]; then
    print_status "Using existing SSH key pair"
else
    print_error "Key file not found: $KEY_FILE"
    exit 1
fi

# Verify public key exists
if [ ! -f "${KEY_FILE}.pub" ]; then
    print_error "Public key not found: ${KEY_FILE}.pub"
    exit 1
fi

echo ""
echo "========================================="
echo "  Public Key (Add to VM)"
echo "========================================="
echo ""
echo "Add this public key to the VM's deployuser authorized_keys file:"
echo ""
cat "${KEY_FILE}.pub"
echo ""
print_info "Command to add to VM (run as root/sudo):"
echo ""
echo "  echo \"$(cat "${KEY_FILE}.pub")\" >> /home/$DEPLOYMENT_USER/.ssh/authorized_keys"
echo ""

echo "========================================="
echo "  Private Key (Add to GitHub Secrets)"
echo "========================================="
echo ""
print_warning "KEEP THIS PRIVATE! Add to GitHub Secrets as: DEPLOY_SSH_KEY"
echo ""
cat "$KEY_FILE"
echo ""

echo "========================================="
echo "  SSH Config Snippet"
echo "========================================="
echo ""
print_info "Add this to your ~/.ssh/config for easy connection:"
echo ""
cat <<EOF
Host $AZURE_VM_NAME
  HostName <VM_PUBLIC_IP>
  User $DEPLOYMENT_USER
  IdentityFile $KEY_FILE
  StrictHostKeyChecking accept-new
EOF
echo ""

echo "========================================="
echo "  GitHub Secrets to Configure"
echo "========================================="
echo ""
print_info "Add these secrets to your GitHub repository:"
echo ""
echo "  DEPLOY_SSH_KEY      Private key content (shown above)"
echo "  DEPLOY_HOST         VM public IP address"
echo "  DEPLOY_USER         $DEPLOYMENT_USER"
echo "  DOTENV_KEY          Production decryption key from .env.vault"
echo ""
print_info "To get DOTENV_KEY:"
echo "  cd backend && npx dotenv-vault@latest keys"
echo "  Look for: DOTENV_KEY_PRODUCTION"
echo ""

echo "========================================="
echo "  Testing SSH Connection"
echo "========================================="
echo ""
print_info "After adding the public key to the VM, test with:"
echo ""
echo "  ssh -i $KEY_FILE $DEPLOYMENT_USER@<VM_PUBLIC_IP>"
echo ""
print_warning "Make sure to replace <VM_PUBLIC_IP> with the actual IP address"
echo ""

print_status "SSH keys generated successfully!"
echo ""
print_info "Key files location:"
echo "  Private: $KEY_FILE"
echo "  Public:  ${KEY_FILE}.pub"
echo ""
