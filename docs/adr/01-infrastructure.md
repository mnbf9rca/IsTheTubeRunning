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
