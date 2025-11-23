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
