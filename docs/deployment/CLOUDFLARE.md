# Cloudflare Configuration

## DNS Setup

**Domain**: `isthetube.cynexia.com`

**Record Type**: CNAME
**Name**: `isthetube`
**Content**: `6bc48aaa-4bdd-412c-9182-568f562a57e0.cfargotunnel.com`
**Proxy Status**: Proxied (orange cloud enabled)
**TTL**: Auto

## SSL/TLS Settings

**Mode**: Full or Flexible (configured on public side)

No origin certificates required on the VM - Cloudflare Tunnel handles all encryption between Cloudflare Edge and the origin.

## WAF (Web Application Firewall)

**Status**: Enabled
**Ruleset**: Default configuration

## Cloudflare Tunnel Architecture

```
Internet
  ↓
Cloudflare Edge (SSL/TLS termination, WAF)
  ↓
Encrypted Tunnel (outbound-only connection from VM)
  ↓
nginx container (no published ports 80/443)
  ↓
Backend services
```

**Key Points**:
- No ports 80/443 published on VM (eliminates Docker/UFW firewall bypass)
- Traffic flows through Cloudflare Tunnel, not directly to VM IP
- VM IP (4.250.90.168) is ephemeral and irrelevant for traffic routing
- Tunnel token configured in `backend/.env.production` as `CLOUDFLARE_TUNNEL_TOKEN`
- `cloudflared` service in `docker-compose.prod.yml` handles tunnel connection

## Verification

Check DNS propagation:
```bash
nslookup isthetube.cynexia.com
dig isthetube.cynexia.com
```

Check Cloudflare proxy is active:
```bash
curl -I https://isthetube.cynexia.com
# Look for cf-ray and cf-cache-status headers
```

## SSH Access

SSH uses traditional networking (not Cloudflare Tunnel):
- Port 22 protected by Azure NSG + UFW + fail2ban
- No Cloudflare proxy for SSH traffic
