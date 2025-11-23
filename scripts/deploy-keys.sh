#!/usr/bin/env bash
# Generate SSH deployment keys for CI/CD
# This is a STUB script - full implementation will be in Issue #241

set -euo pipefail

# Source Azure configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./azure-config.sh
source "$SCRIPT_DIR/azure-config.sh"

echo "=== SSH Deployment Keys Generation (STUB - Issue #241) ==="
echo ""
echo "This script will generate SSH keys for automated deployment:"
echo "  - Key Name: $AZURE_SSH_KEY_NAME"
echo "  - Key Type: ed25519 (modern, secure)"
echo "  - Purpose: GitHub Actions → Azure VM deployment"
echo ""
echo "Full implementation tasks (Issue #241):"
echo "  1. Generate ed25519 key pair"
echo "     ssh-keygen -t ed25519 -f ~/.ssh/$AZURE_SSH_KEY_NAME -C 'github-actions-deploy'"
echo "  2. Display public key (add to VM authorized_keys)"
echo "  3. Display private key (add to GitHub Secrets as DEPLOY_SSH_KEY)"
echo "  4. Create SSH config snippet for easy connection:"
echo ""
echo "     Host $AZURE_VM_NAME"
echo "       HostName <VM_PUBLIC_IP>"
echo "       User $DEPLOYMENT_USER"
echo "       IdentityFile ~/.ssh/$AZURE_SSH_KEY_NAME"
echo "       StrictHostKeyChecking accept-new"
echo ""
echo "  5. Test connection: ssh $DEPLOYMENT_USER@<VM_PUBLIC_IP>"
echo ""
echo "GitHub Secrets to configure (Issue #241):"
echo "  - DEPLOY_SSH_KEY: Private key content"
echo "  - DEPLOY_HOST: VM public IP"
echo "  - DEPLOY_USER: $DEPLOYMENT_USER"
echo "  - DOTENV_KEY: Production decryption key from .env.vault"
echo ""
echo "NOTE: This is a stub. Actual key generation will be implemented in Issue #241."
