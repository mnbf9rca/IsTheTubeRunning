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

## Cloudflare Tunnel (Zero Trust Ingress)

### Status
Active

### Context
Docker publishes container ports using iptables NAT table manipulation, which processes packets **before** they reach UFW's INPUT chain. This means Docker completely bypasses UFW firewall rules for published ports (e.g., `-p 80:80`).

The original architecture intended to use UFW to restrict ports 80/443 to Cloudflare IP ranges only, but this is ineffective for Docker-published ports. Direct access to the VM's public IP on port 80 would bypass both Cloudflare and UFW, exposing the application to:
- Cloudflare WAF bypass (direct access skips WAF rules)
- DDoS attacks (no Cloudflare protection layer)
- SSL/TLS bypass (plain HTTP to VM instead of HTTPS via Cloudflare)

See: https://docs.docker.com/engine/network/packet-filtering-firewalls/

Alternatives considered:
1. **DOCKER-USER iptables chain**: Add custom iptables rules for Cloudflare IP filtering (complex, requires iptables expertise)
2. **Localhost binding + host nginx**: Bind containers to 127.0.0.1, run nginx on host (extra layer, two nginx configs)
3. **Cloudflare Tunnel**: Outbound-only encrypted tunnel, no published ports (eliminates problem entirely)

### Decision
Use **Cloudflare Tunnel** (Zero Trust) for all HTTP/HTTPS ingress. Remove port publishing entirely from docker-compose configuration.

**Architecture:**
```
Internet → Cloudflare Edge → Encrypted Tunnel (outbound-only) → nginx container (no published ports)
SSH     → Azure NSG → UFW → host SSH daemon (traditional networking, port 22)
```

**Implementation:**
- Add `cloudflared` container to docker-compose.prod.yml with CLOUDFLARE_TUNNEL_TOKEN
- Remove `ports: - "80:80"` from nginx service (no published ports)
- Remove HTTP/HTTPS NSG rules from provision-azure-vm.sh (not needed)
- Simplify UFW configuration to SSH protection only (ports 80/443 not published)

### Consequences
**Easier:**
- **Eliminates Docker/UFW firewall bypass issue** entirely (no ports to bypass)
- **Zero-maintenance security**: Cloudflare manages ingress, no IP whitelist updates needed
- Free tier (no cost): Cloudflare Tunnel included in free plan
- Better security: No open inbound ports 80/443 on VM, outbound-only tunnel
- Automatic failover: Cloudflare handles routing to healthy tunnels
- Built-in DDoS protection: Traffic must pass through Cloudflare edge
- Geographic distribution: Cloudflare's global network routes users to nearest edge

**More Difficult:**
- Cloudflare dependency: Application requires Cloudflare service (already the case for DNS/proxy)
- Slight latency increase: ~10-30ms added for tunnel routing (acceptable for hobby project)
- Token management: CLOUDFLARE_TUNNEL_TOKEN must be securely stored and rotated if compromised
- Debugging: Cannot directly access application on VM (must go through tunnel)

**SSH Access:**
- SSH remains on traditional networking (port 22, Azure NSG + UFW + fail2ban protected)
- Cloudflare Tunnel **only affects HTTP/HTTPS traffic**
- No changes to SSH security model

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

---

## Automatic Security Updates

### Status
Active

### Context
Production servers require timely security patches to protect against vulnerabilities. Manual updates are error-prone and require constant monitoring. Ubuntu provides `unattended-upgrades` for automatic security patch installation.

Key consideration: Kernel security updates require system reboots to take effect. Without automatic reboots, systems can run with unpatched kernels indefinitely, remaining vulnerable even after patches are downloaded.

### Decision
Configure `unattended-upgrades` on all production VMs with:
- **Security updates only** (not general feature updates)
- **Automatic reboot enabled** at 3 AM UTC when kernel/critical updates require it
- **Docker packages blacklisted** for manual control
- **Daily update schedule** (default Ubuntu behavior)

Implementation in `deploy/setup/12-configure-unattended-upgrades.sh`:
- Install `unattended-upgrades` package
- Configure `/etc/apt/apt.conf.d/20auto-upgrades` to enable daily updates
- Configure `/etc/apt/apt.conf.d/50unattended-upgrades` with security-only policy
- Set `Automatic-Reboot "true"` with reboot time at `"03:00"` (3 AM UTC)
- Blacklist `docker-ce`, `docker-ce-cli`, `containerd.io` packages
- Enable systemd timers for automatic execution

### Consequences
**Easier:**
- Security patches applied automatically without manual intervention
- Kernel vulnerabilities patched effectively (reboots ensure new kernels activate)
- Reduced risk of running vulnerable systems
- Compliance with security best practices
- Automated cleanup of old kernel packages and unused dependencies
- Detailed logs in `/var/log/unattended-upgrades/` for audit trail

**More Difficult:**
- **Unexpected downtime** from automatic reboots (mitigated by 3 AM UTC scheduling)
- Docker containers restart after reboot (handled by systemd auto-start service)
- Must monitor `/var/run/reboot-required` if auto-reboot disabled
- Docker updates must be managed manually (security vs stability tradeoff)
- No email notifications by default (Azure blocks SMTP port 25, would need relay)

**Reboot Rationale:**
Automatic reboots are critical for security. Without them:
- Downloaded kernel patches remain inactive until manual reboot
- Systems appear "patched" but still run vulnerable kernels
- Security compliance tools may miss this gap
- Manual reboot scheduling often gets forgotten or delayed

The 3 AM UTC timing minimizes user impact during typical low-traffic hours. For applications requiring high availability, the systemd auto-start service ensures containers restart automatically after reboot.

---

## Docker Compose Service Dependencies

### Status
Active

### Context
Docker Compose `depends_on` with health conditions creates hard dependencies between services. Over-constrained dependencies can cause complete service failures during troubleshooting:
- `cloudflared` waiting for `nginx` health → Backend failure prevents tunnel connection → Complete external blackout (no 502 errors, just timeouts)
- `nginx` waiting for `backend` health → Backend issues block nginx startup → Cannot troubleshoot via external requests

Relaxing dependencies allows infrastructure (nginx, cloudflared) to start independently, enabling operational visibility even when application services fail.

### Decision
Use minimal service dependencies to allow independent startup and better troubleshooting:

1. **cloudflared**: No dependencies on nginx
   - Rationale: Cloudflare Tunnel is infrastructure, not application
   - Allows tunnel to connect even if nginx/backend broken
   - Cloudflare returns 502 Bad Gateway (helpful) instead of connection timeout (unhelpful)

2. **nginx**: Depends only on frontend init container with `condition: service_completed_successfully`
   - No backend dependency - serves static files immediately
   - Rationale: nginx can serve frontend and return 502 for API requests if backend unavailable
   - Faster startup (no health check waiting)
   - Better troubleshooting (502 errors show what's broken)
   - Health check tests nginx itself (serving frontend) not backend proxy

3. **backend/celery-worker**: Keep `condition: service_healthy` for postgres/redis
   - Rationale: These services require database connectivity to function
   - Health checks ensure connection pools can be established

### Consequences
**Easier:**
- External access maintained during backend failures (troubleshooting via 502 errors)
- Cloudflare Tunnel connects independently of application health
- Faster service startup (nginx doesn't wait for backend health)
- Better operational visibility (can diagnose issues via external requests)
- Service recovery without manual tunnel restart

**More Difficult:**
- Services may start in "degraded" state (nginx running but backend unhealthy)
- Health check endpoints may show errors during startup (expected behavior)
- Must monitor logs/health endpoints rather than relying on container startup status alone

---

## PostgreSQL 18 Volume Mount

### Status
Active

### Context
PostgreSQL 18 changed the default data directory structure to align with `pg_ctlcluster` conventions (Debian/Ubuntu standard). The new pattern uses `/var/lib/postgresql` as the mount point, with PostgreSQL automatically creating `/var/lib/postgresql/data` subdirectory.

Mounting directly to `/var/lib/postgresql/data` (old pattern) bypasses this structure and causes warnings:
```
Error: in 18+, these Docker images are configured to store database data in a
       format which is compatible with "pg_ctlcluster" (specifically, using
       major-version-specific directory names).
```

See: https://github.com/docker-library/postgres/pull/1259

### Decision
Mount PostgreSQL volume to `/var/lib/postgresql` (parent directory) in production, matching development configuration:
- **Production**: `postgres_data:/var/lib/postgresql`
- **Development**: Already correct (`docker-compose.yml` line 14)

PostgreSQL 18 creates `/var/lib/postgresql/data` automatically, following `pg_ctlcluster` conventions.

### Consequences
**Easier:**
- No PostgreSQL 18 compatibility warnings
- Proper major-version-specific directory structure
- Supports `pg_upgrade --link` for future upgrades (avoids mount point boundary issues)
- Production and development configs aligned (consistency)

**More Difficult:**
- **BREAKING CHANGE**: Existing data at `/data` mount won't be accessible after change
- Requires data migration or fresh start (Issue #266 confirmed fresh deployment acceptable)
- Different from pre-18 PostgreSQL patterns (legacy documentation may be incorrect)

---

## Systemd Service Management

### Status
Active

### Context
Systemd service for Docker Compose manages the application lifecycle on production VMs. The ExecStop command determines how containers are stopped:
- `docker compose down`: Stops and **removes** containers (full cleanup, slower restart)
- `docker compose stop`: Stops containers with SIGTERM, **containers remain in stopped state** (faster restart)

For production deployments with frequent restarts (deployments, debugging), container preservation provides faster recovery without requiring full recreation.

### Decision
Use `docker compose stop` in ExecStop for graceful shutdown with container preservation:

```bash
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml stop
```

Keep `Type=simple` with foreground `docker compose up --no-log-prefix` (no `--detach` flag):
- Systemd tracks the docker compose process directly
- Proper signal handling (SIGTERM cascades to containers)
- Service logs visible via journalctl

### Consequences
**Easier:**
- Faster service restarts (containers not recreated)
- Container state preserved (volumes, networks remain intact)
- Graceful shutdown (SIGTERM allows cleanup)
- Explicit service lifecycle (systemd manages process directly)

**More Difficult:**
- Containers persist in "exited" state after stop (not removed)
- Manual cleanup required for complete removal (`docker compose down`)
- Must use `systemctl restart` or `docker compose up` to resume containers

---

## GitHub Actions CI/CD with GHCR

### Status
Active

### Context
The existing CI workflow runs tests and linting, but deployment was manual (SSH to VM, pull code, build images directly on VM). This was slow (~5-10 minutes image builds) and error-prone (no atomic deploys). Need automated deployment triggered by pushes to release branch.

Options considered:
1. **Build on VM**: Current manual approach - slow, blocks VM resources during build
2. **Build in Actions, push to Docker Hub**: External dependency, rate limits on free tier (200 pulls/6hrs)
3. **Build in Actions, push to GHCR**: Integrated with GitHub, free unlimited pulls for public repos, automatic authentication

### Decision
Use GitHub Actions to build Docker images and push to GitHub Container Registry (GHCR). Deploy via SSH to Azure VM using OIDC for dynamic NSG IP whitelisting.

**Workflow:**
1. Push to `release` branch triggers deployment (PR-based: main → release)
2. Build backend and frontend images in parallel (2-3 minutes total)
3. Push images to GHCR with `:latest` and `sha-<commit>` tags
4. Azure OIDC login for NSG access (no long-lived credentials)
5. Temporarily whitelist GitHub Actions runner IP in NSG (30s propagation)
6. SSH to VM as `deployuser`, execute `deploy.sh` script:
   - Pull latest code from release branch
   - Pull new images from GHCR (`docker compose pull`)
   - Restart services (`docker compose up -d --remove-orphans`)
   - Health check (curl localhost/health)
7. External health check (https://isthetube.cynexia.com/health via Cloudflare Tunnel)
8. Remove temporary NSG rule (cleanup runs `if: always()`)

**Release Strategy:**
- Development on feature branches → PRs merge to `main` (runs CI tests)
- PRs from `main` → `release` trigger deployment (explicit production releases)
- Provides control over production releases vs continuous deployment

**VM IP Discovery:**
- Dynamically query VM public IP using `az vm list-ip-addresses`
- No hardcoded IP secrets needed (config from `deploy/azure-config.json`)

### Consequences
**Easier:**
- Fast deployments (images pre-built in CI, VM just pulls and restarts ~2 minutes vs 10+ minutes)
- Reproducible builds (same GHCR image in multiple environments)
- Audit trail (image tags match commit SHAs, GHCR tracks all pushes)
- No Docker Hub rate limits (GHCR integrated with GitHub)
- Secure SSH access (dynamic IP whitelisting via OIDC, short-lived NSG rules)
- No hardcoded IP secrets (query from Azure dynamically)
- Atomic deployments (all images built before deploy starts)
- Parallel builds (backend + frontend in ~3 minutes vs sequential ~8 minutes)

**More Difficult:**
- Azure OIDC setup required (one-time manual configuration: App Registration, Federated Credentials, IAM)
- Need to manage GHCR image retention/cleanup (manually set packages to public after first push)
- Two-branch workflow (main + release) requires discipline (but provides safety)
- NSG rule propagation delay (~30 seconds before SSH works)
- Must have GitHub Variables configured: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`
- Must have GitHub Secret configured: `DEPLOY_SSH_KEY`

---

## Azure OIDC for GitHub Actions

### Status
Active

### Context
GitHub Actions needs to modify Azure NSG rules to allow SSH access from dynamic runner IPs (changes per workflow run). Options for Azure authentication:
1. **Service Principal with secret**: Long-lived credential stored in GitHub Secrets, requires rotation, broad exposure risk
2. **OIDC federated credentials**: No secrets stored, short-lived tokens, scoped to specific workflows/branches

### Decision
Use Azure OIDC (OpenID Connect) with federated credentials for GitHub Actions authentication. Configure with minimal permissions (Network Contributor scoped to `isthetube-prod` resource group).

**Configuration:**
- Microsoft Entra ID App Registration: `github-actions-isthetube`
- Federated credential: scoped to `mnbf9rca/IsTheTubeRunning` repository, `release` branch only
- IAM role assignment: Network Contributor on `isthetube-prod` resource group
- Workflow uses `azure/login@v2` with `id-token: write` permission
- GitHub Variables: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` (no client secret)
- GitHub Secret: `DEPLOY_SSH_KEY` (private SSH key for deployuser)

**Why Network Contributor:**
- Only permission needed: create/delete NSG rules for temporary SSH access
- Does not grant access to read VM data, modify VMs, or access other resources
- Scoped to single resource group (cannot affect other Azure resources)

### Consequences
**Easier:**
- No secret rotation (OIDC tokens are short-lived, issued per workflow run)
- Scoped access (only release branch can authenticate, only NSG modifications allowed)
- Azure best practice for GitHub Actions (Microsoft-recommended approach)
- Better security audit trail (Azure logs show OIDC authentication with branch context)

**More Difficult:**
- Initial setup requires Azure Portal access (create App Registration, configure federated credentials)
- Must document setup steps for future maintainers (see `docs/deployment/CI-CD.md`)
- Cannot test OIDC authentication locally (only works from GitHub Actions runners)
