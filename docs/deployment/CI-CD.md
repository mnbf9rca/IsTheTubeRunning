# CI/CD Deployment Guide

This document describes the automated CI/CD pipeline for IsTheTubeRunning using GitHub Actions and GitHub Container Registry (GHCR).

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Azure OIDC Setup](#azure-oidc-setup)
- [GitHub Configuration](#github-configuration)
- [How Deployments Work](#how-deployments-work)
- [Manual Rollback](#manual-rollback)
- [Troubleshooting](#troubleshooting)

---

## Overview

### Architecture

```
Developer → main branch → CI Tests Pass → PR to release → Auto Deploy

GitHub Actions:
1. Build images (backend, frontend) in parallel
2. Push to GHCR with :latest and sha-<commit> tags
3. Azure OIDC login
4. Query VM IP from Azure
5. Temporarily whitelist runner IP in NSG
6. SSH deploy → pull code → pull images → restart → health check
7. External health check via Cloudflare Tunnel
8. Clean up temporary NSG rule
```

### Key Features

- **Fast deployments**: Pre-built images (~2 min vs 10+ min building on VM)
- **Atomic releases**: All images built before deployment starts
- **Audit trail**: Image tags match commit SHAs
- **Secure**: OIDC authentication, dynamic NSG rules, no long-lived credentials
- **Controlled**: Release branch provides manual approval step

---

## Prerequisites

### Required Access

1. **Azure Portal access** with permissions to:
   - Create App Registrations in Azure AD
   - Assign IAM roles to resource groups
   - View NSG rules (for troubleshooting)

2. **GitHub repository admin** access to:
   - Add GitHub Variables and Secrets
   - Manage environments (production environment)
   - View Actions workflow runs

3. **VM SSH access** as `deployuser` for:
   - Manual rollback
   - Debugging deployment issues

### Required Files

These files must already exist (created in issues #240-243):

- `deploy/docker-compose.prod.yml` - Production compose config
- `deploy/azure-config.json` - Azure resource configuration
- `deploy/scripts/deploy.sh` - Deployment script
- `deploy/scripts/rollback.sh` - Rollback script
- `.env.vault` - Encrypted production secrets
- `.github/workflows/deploy.yml` - Deployment workflow

---

## Azure OIDC Setup

This is a **one-time manual setup** required before the first deployment.

### Step 1: Create Azure AD App Registration

1. Go to **Azure Portal** → **Microsoft Entra ID** → **App registrations**
2. Click **"New registration"**
3. Configure:
   - **Name**: `github-actions-isthetube`
   - **Supported account types**: "Accounts in this organizational directory only (Single tenant)"
   - **Redirect URI**: Leave blank
4. Click **"Register"**
5. **Save these values** (needed for GitHub Variables):
   - **Application (client) ID** → `AZURE_CLIENT_ID`
   - **Directory (tenant) ID** → `AZURE_TENANT_ID`

### Step 2: Configure Federated Credentials

1. In the App Registration, go to **"Certificates & secrets"**
2. Click the **"Federated credentials"** tab
3. Click **"Add credential"**
4. Configure:
   - **Federated credential scenario**: "GitHub Actions deploying Azure resources"
   - **Organization**: `mnbf9rca`
   - **Repository**: `IsTheTubeRunning`
   - **Entity type**: "Branch"
   - **GitHub branch name**: `release`
   - **Name**: `github-actions-release-branch`
5. Click **"Add"**

**Security Note:** This configuration means only GitHub Actions workflows running on the `release` branch in the `mnbf9rca/IsTheTubeRunning` repository can authenticate to Azure. Other branches, forks, or repositories cannot authenticate.

### Step 3: Grant NSG Permissions

1. Go to **Azure Portal** → **Resource Groups** → **isthetube-prod**
2. Click **"Access control (IAM)"** in the left sidebar
3. Click **"Add role assignment"**
4. On the **"Role"** tab:
   - Search for and select **"Network Contributor"**
   - Click **"Next"**
5. On the **"Members"** tab:
   - **Assign access to**: "User, group, or service principal"
   - Click **"+ Select members"**
   - Search for: `github-actions-isthetube`
   - Select the App Registration created in Step 1
   - Click **"Select"**
   - Click **"Next"**
6. On the **"Review + assign"** tab:
   - Click **"Review + assign"**

**Why Network Contributor?** This role allows creating/deleting NSG rules for temporary SSH access. It does NOT grant permissions to read VM data, modify VMs, or access other Azure resources. The role is scoped to the `isthetube-prod` resource group only.

**Note:** OIDC federated credentials cannot be tested locally - they only work from GitHub Actions runners. The first deployment workflow run will validate the setup.

---

## GitHub Configuration

### Variables (Public Identifiers)

Add these variables in GitHub repository **Settings** → **Secrets and variables** → **Actions** → **Variables** tab → **New repository variable**:

| Variable Name | Value | Where to Find |
|---------------|-------|---------------|
| `AZURE_CLIENT_ID` | Application (client) ID | Azure Portal → App Registration → Overview |
| `AZURE_TENANT_ID` | Directory (tenant) ID | Azure Portal → App Registration → Overview |
| `AZURE_SUBSCRIPTION_ID` | Azure Subscription ID | Already known: `1d9d2a8a-f001-41ae-a983-2d0cc36f3ea7` |

### Secrets (Sensitive Data)

Add these secrets in GitHub repository **Settings** → **Secrets and variables** → **Actions** → **Secrets** tab → **New repository secret**:

| Secret Name | Value | Where to Find |
|-------------|-------|---------------|
| `DEPLOY_SSH_KEY` | Private SSH key for deployuser | Output from `deploy/deploy-keys.sh --generate` |

**Important:** Do NOT add `AZURE_CLIENT_SECRET` - OIDC federated credentials use short-lived tokens issued per workflow run, not long-lived secrets.

---

## How Deployments Work

### Triggering a Deployment

**Automatic Trigger:**
```bash
# Merge PR from main to release
git checkout main
git pull origin main
git checkout release
git merge main
git push origin release
# GitHub Actions automatically deploys
```

**Manual Trigger:**
```bash
# Via GitHub UI: Actions tab → Deploy to Production → Run workflow → Select branch: release
```

### Deployment Flow

1. **Build Stage** (parallel, ~3 minutes):
   - Backend image built and pushed to `ghcr.io/mnbf9rca/isthetuberunning/backend:latest` and `sha-<commit>`
   - Frontend image built and pushed to `ghcr.io/mnbf9rca/isthetuberunning/frontend:latest` and `sha-<commit>`

2. **Deploy Stage** (~2 minutes):
   - Azure OIDC login (no secrets, uses federated credentials)
   - Query VM public IP from Azure: `az vm list-ip-addresses`
   - Get GitHub Actions runner IP: `curl ifconfig.me`
   - Create temporary NSG rule allowing runner IP → VM port 22
   - Wait 30 seconds for NSG rule propagation
   - SSH to VM as `deployuser`, execute `/opt/isthetube/deploy/scripts/deploy.sh`:
     - Pull latest code from `release` branch
     - Pull new Docker images from GHCR
     - Restart services: `docker compose up -d --remove-orphans`
     - Health check: `curl http://localhost/health`
   - External health check: `curl https://isthetube.cynexia.com/health` (via Cloudflare Tunnel)
   - Delete temporary NSG rule (runs `if: always()` to ensure cleanup even on failure)
   - Azure logout

3. **Success Indicators**:
   - ✅ All jobs green in GitHub Actions
   - ✅ Health check passes
   - ✅ Site accessible at https://isthetube.cynexia.com

### GHCR Package Visibility

After the first deployment, GHCR packages default to private. Make them public:

1. Go to https://github.com/orgs/mnbf9rca/packages
2. Find `isthetuberunning/backend` and `isthetuberunning/frontend`
3. Click each package → **Package settings** → **Change visibility** → **Public**

**Why public?** The VM pulls images without authentication (`docker compose pull` in deploy script). Public packages allow unauthenticated pulls.

---

## Manual Rollback

If a deployment fails or introduces a bug, roll back to a previous version.

### Via SSH (Recommended)

```bash
# 1. SSH to VM
ssh -i ~/.ssh/isthetube-deploy-key deployuser@<VM_IP>

# 2. Find previous working commit
cd /opt/isthetube
git log --oneline -10

# 3. Run rollback script
./deploy/scripts/rollback.sh <commit-sha>

# Example: rollback to previous commit
./deploy/scripts/rollback.sh HEAD~1

# Example: rollback to specific commit
./deploy/scripts/rollback.sh abc1234
```

### Manual Rollback Steps

If the rollback script fails, perform these steps manually:

```bash
# SSH to VM
ssh -i ~/.ssh/isthetube-deploy-key deployuser@<VM_IP>

# Checkout previous version
cd /opt/isthetube
git fetch origin
git checkout <previous-commit-sha>

# Restart services
cd /opt/isthetube/deploy
docker compose -f docker-compose.prod.yml up -d --remove-orphans

# Verify health
curl http://localhost/health
```

### Verify Rollback

```bash
# Check current commit
git rev-parse --short HEAD

# Check running containers
docker compose -f docker-compose.prod.yml ps

# Check recent logs
docker compose -f docker-compose.prod.yml logs --tail=100

# Test externally
curl https://isthetube.cynexia.com/health
```

---

## Troubleshooting

### Build Stage Failures

#### Error: "failed to solve with frontend dockerfile.v0"

**Cause:** Dockerfile syntax error or missing dependency.

**Fix:**
```bash
# Test build locally
docker build -t test-backend ./backend
docker build -t test-frontend ./frontend
```

#### Error: "denied: permission_denied"

**Cause:** GITHUB_TOKEN lacks packages:write permission.

**Fix:** Check `.github/workflows/deploy.yml` has:
```yaml
permissions:
  packages: write
```

### Deploy Stage Failures

#### Error: "AADSTS700016: Application with identifier was not found"

**Cause:** `AZURE_CLIENT_ID` secret is incorrect or App Registration deleted.

**Fix:**
1. Verify App Registration exists in Azure Portal
2. Update `AZURE_CLIENT_ID` secret in GitHub

#### Error: "az: command not found"

**Cause:** Azure CLI not available on GitHub Actions runner.

**Fix:** Add to workflow before `az` commands:
```yaml
- name: Install Azure CLI
  run: curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

**Note:** `ubuntu-latest` runners include `az` by default, so this should not occur.

#### Error: "NSG rule create failed: The client does not have authorization"

**Cause:** App Registration missing Network Contributor role on resource group.

**Fix:**
1. Go to Azure Portal → Resource Groups → isthetube-prod → IAM
2. Verify `github-actions-isthetube` has "Network Contributor" role
3. If missing, add per [Azure OIDC Setup Step 3](#step-3-grant-nsg-permissions)

#### Error: "SSH connection refused" or "Connection timed out"

**Possible Causes:**
1. NSG rule not propagated yet (wait longer than 30s)
2. Runner IP changed between NSG rule creation and SSH attempt
3. VM is down
4. SSH service not running on VM

**Fix:**
```bash
# Check NSG rules in Azure Portal
Azure Portal → Network Security Groups → isthetube-nsg → Inbound security rules
# Look for a rule named "AllowGitHubRunner-<run_id>" (e.g., "AllowGitHubRunner-123456") with priority 900

# If rule exists but SSH fails, wait and retry (NSG propagation can take up to 2 minutes)

# Check VM status
az vm get-instance-view --resource-group isthetube-prod --name isthetube-vm --query instanceView.statuses
```

#### Error: "Health check failed after 2 minutes"

**Cause:** Services failed to start or backend unhealthy.

**Fix:** SSH to VM and check logs:
```bash
ssh -i ~/.ssh/isthetube-deploy-key deployuser@<VM_IP>
cd /opt/isthetube/deploy

# Check container status
docker compose -f docker-compose.prod.yml ps

# Check logs for errors
docker compose -f docker-compose.prod.yml logs backend
docker compose -f docker-compose.prod.yml logs postgres
docker compose -f docker-compose.prod.yml logs redis

# Check health endpoint locally
curl -v http://localhost/health

# Check Cloudflare Tunnel status
docker compose -f docker-compose.prod.yml logs cloudflared
```

### GHCR Image Pull Failures

#### Error: "Error response from daemon: pull access denied"

**Cause:** GHCR packages are private and VM has no authentication.

**Fix:** Make packages public:
1. Go to https://github.com/orgs/mnbf9rca/packages
2. Find package → Package settings → Change visibility → Public

### Cleanup Failures

#### Warning: "NSG rule 'AllowGitHubRunner-<run_id>' not found"

**Cause:** The workflow creates NSG rules with names like `AllowGitHubRunner-<run_id>` (e.g., `AllowGitHubRunner-123456`). This warning appears if the rule for the current run ID was already deleted or never created.

**Impact:** None - cleanup is idempotent.

**Fix:** No action needed (warning is expected if the rule with the specific run ID doesn't exist).

---

## Best Practices

1. **Always test in feature branch first**: Merge feature → main, verify CI tests pass, then merge main → release
2. **Monitor first deployment closely**: Watch GitHub Actions logs and SSH to VM to check container status
3. **Keep release branch protected**: Require PR reviews for merging to release
4. **Tag releases**: After successful deployment, tag the commit: `git tag v1.0.0 && git push origin v1.0.0`
5. **Document failed deployments**: If rollback is needed, document the issue in GitHub Issue or PR for future reference

---

## Related Documentation

- [Azure OIDC ADR](../adr/01-infrastructure.md#azure-oidc-for-github-actions)
- [GitHub Actions CI/CD ADR](../adr/01-infrastructure.md#github-actions-cicd-with-ghcr)
- [Cloudflare Tunnel Setup](./CLOUDFLARE.md)
- [Auth0 Setup](./AUTH0.md)
