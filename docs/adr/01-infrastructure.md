# Project Structure & Infrastructure

## Monorepo Structure

### Status
Active

### Context
Need to organize backend (FastAPI), frontend (React), and shared types in a way that's manageable for a hobby project while allowing code sharing and coordinated changes.

### Decision
Use a monorepo structure with `/backend`, `/frontend`, and `/shared` directories at the root level. Both backend and frontend can import from shared types when needed.

### Consequences
**Easier:**
- Coordinated changes across frontend and backend in a single commit
- Shared type definitions reduce duplication
- Single repository to clone and manage
- Simplified CI/CD (single workflow file)

**More Difficult:**
- Larger repository size
- Need to manage dependencies for multiple projects
- Could have conflicts if multiple developers work in different areas (not a concern for hobby project)

---

## Azure VM + Docker Compose Deployment

### Status
Active

### Context
Need a cost-effective deployment solution within Azure's free credits ($150/month) that provides full control over infrastructure and avoids per-service pricing of managed services.

### Decision
Deploy to a single Azure VM (Standard D2s_v3: 2 vCPU, 8GB RAM) using Docker Compose to orchestrate all services (PostgreSQL, Redis, FastAPI, Celery, Nginx).

### Consequences
**Easier:**
- Full control over all infrastructure
- Predictable monthly cost (~$70-95/month, well within budget)
- No per-service pricing surprises
- Simple backup strategy (VM snapshots + database dumps)
- Easy to replicate environment locally

**More Difficult:**
- Manual VM management (updates, monitoring)
- Single point of failure (no automatic failover)
- Need to handle scaling manually if traffic grows
- Responsible for all security patches

---

## Cloudflare + UFW Firewall

### Status
Active

### Context
Need WAF, SSL termination, CDN, and DDoS protection without additional cost. Also need to restrict direct access to VM for security.

### Decision
Use Cloudflare free tier for WAF, SSL, and CDN. Configure UFW firewall on VM to only accept traffic from Cloudflare IP ranges on ports 80/443. Allow SSH from specific IP or all (configurable).

### Consequences
**Easier:**
- Free WAF, SSL certificates, and CDN
- DDoS protection included
- Easy SSL/TLS management (no Let's Encrypt maintenance)
- Origin server protected from direct attacks
- Weekly updates to Cloudflare IP ranges via script

**More Difficult:**
- Dependency on Cloudflare service
- Must maintain Cloudflare IP whitelist
- Debugging can be harder (traffic passes through Cloudflare)
- Limited to Cloudflare's free tier features

---

## SSH Access IP Restriction

### Status
Active

### Context
Azure Network Security Group (NSG) rules control inbound traffic to the VM. Opening SSH (port 22) to the entire internet (`*`) exposes the VM to attacks, even with key-only authentication. However, requiring users to manually configure their IP address creates friction in the provisioning process.

### Decision
Auto-detect the user's current public IP address during VM provisioning and configure the NSG SSH rule to only allow access from that IP (/32). Provide override via `AZURE_SSH_SOURCE_PREFIXES` environment variable for custom IP ranges. Document that additional IPs can be added later via Azure Portal.

Implementation in `deploy/provision-azure-vm.sh`:
- Use `curl -s ifconfig.me` to detect current IP
- Add detected IP/32 to NSG SSH rule
- Allow override via `AZURE_SSH_SOURCE_PREFIXES` env var
- Error if detection fails and env var not set

### Consequences
**Easier:**
- Secure by default (SSH not open to world)
- No manual IP lookup required
- Works immediately for provisioning user
- Additional IPs easily added via Azure Portal
- Override available for advanced users or CI/CD

**More Difficult:**
- Users on dynamic IPs may need to update NSG when IP changes
- Multi-user teams need to add each user's IP via Portal
- Requires internet connectivity during provisioning

---

## SSH-Based CI/CD Deployment

### Status
Active

### Context
Need automated deployment pipeline from GitHub to Azure VM. Options considered:
1. Azure DevOps Pipelines (managed CI/CD service)
2. GitHub Actions with Azure deployment actions (managed deployment)
3. GitHub Actions with direct SSH deployment (self-managed)

For a hobby project with cost constraints and desire for infrastructure control, need to balance automation with complexity and cost.

### Decision
Use GitHub Actions with direct SSH deployment to Azure VM. Deployment process:
1. GitHub Actions runs tests and builds Docker images
2. SSH into Azure VM using deployment key (stored in GitHub Secrets)
3. Pull latest code, run docker-compose commands
4. Run health checks to verify deployment

Configuration managed through:
- `scripts/azure-config.sh`: Centralized Azure configuration
- `docker-compose.prod.yml`: Production service definitions
- `.env.vault`: Encrypted secrets (decrypted via DOTENV_KEY)
- `docker/scripts/`: Operational scripts (backup, health check, UFW)

### Consequences
**Easier:**
- Full control over deployment process (no abstraction layers)
- No additional Azure service costs (just VM)
- Simple debugging (SSH into VM, check logs directly)
- Easy to test deployment locally (same Docker Compose config)
- Transparent process (can see exactly what happens during deployment)
- Infrastructure as code (all scripts in repository)
- Secrets managed with dotenv-vault (single DOTENV_KEY in GitHub Secrets)

**More Difficult:**
- Manual responsibility for deployment script maintenance
- No built-in rollback mechanisms (must implement manually)
- SSH key management required (though simpler than managed service auth)
- Need to handle deployment failures explicitly
- No deployment dashboard/UI (command-line only)
- Scaling deployment to multiple VMs requires custom orchestration

---

## Deployment Script Design Principles

### Status
Active

### Context
Setup scripts for VM provisioning must be reliable, idempotent, and maintainable. These scripts run sequentially with dependencies, and partial failures can leave the system in an inconsistent state. Manual VM provisioning (Issue 241) requires deterministic configuration where each step depends on previous steps completing successfully.

### Decision
All deployment scripts (`deploy/provision-azure-vm.sh`, `deploy/setup-vm.sh`, and `deploy/setup/*.sh`) follow these principles:

1. **Idempotency**: Scripts can be run multiple times safely, detecting and preserving existing configuration
2. **Sequential Dependencies**: Setup subscripts run in order (01 → 10), each depending on previous steps
3. **Fail-Fast**: Any subscript failure stops execution immediately (configuration is deterministic)
4. **Single Responsibility**: Each subscript handles one concern (system update, Docker, UFW, etc.)
5. **Dependency Management**: Dependencies installed once in earliest script, checked (not re-installed) in later scripts
6. **Timestamped Backups**: Configuration backups use timestamps (e.g., `.backup.20231224-153045`) to preserve history

### Consequences
**Easier:**
- Predictable behavior on repeated runs
- Clear error messages (no cascading failures from dependencies)
- Easy to understand what each script does
- Safe to re-run after failures (fix issue and re-run setup-vm.sh)
- Dependencies managed in single location (01-system-update.sh)
- Configuration history preserved via timestamped backups

**More Difficult:**
- Must carefully check for existing configuration in each script
- Scripts must handle both fresh installs and updates
- Error handling must be comprehensive
- Cannot skip failed steps (must fix and re-run)
