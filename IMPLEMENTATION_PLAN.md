# TfL Disruption Alert System - Implementation Plan

## Project Overview
Monorepo with FastAPI backend, React frontend, Celery worker for alert processing, deployed to Azure VM with Docker Compose.

## Architecture Decisions
- **Auth**: Auth0 with local testing mocks
- **Structure**: Monorepo (backend + frontend + shared types)
- **Routes**: Multi-line routes with interchange validation via station graph
- **Alerts**: Celery + Redis for background processing
- **Validation**: Numeric codes for both email and SMS
- **Deployment**: Azure VM (Standard D2s_v3) with Docker Compose
- **Security**: Cloudflare WAF + UFW firewall rules (Cloudflare IPs only)
- **Dev Environment**: Docker Compose with Colima

## Technology Stack & Versions

### Core Languages & Runtimes
- **Python**: 3.14 (managed with uv)
- **Node.js**: 24 LTS
- **TypeScript**: 5.9

### Backend
- **FastAPI**: ~0.115.0
- **SQLAlchemy**: ~2.0 (async support)
- **Alembic**: Latest (for migrations)
- **Pydantic**: ~2.0
- **pydantic_tfl_api**: Latest
- **Celery**: ~5.4.0
- **Mypy**: Latest (strict mode)
- **Ruff**: Latest (formatting & linting)
- **Pytest**: Latest with pytest-asyncio

### Frontend
- **React**: 19
- **Vite**: ~7
- **shadcn/ui**: Latest (canary for React 19)
- **Tailwind CSS**: v4
- **React Router**: Latest
- **Recharts**: Latest (for admin dashboard)

### Infrastructure
- **PostgreSQL**: 18
- **Redis**: 8.2.1
- **Nginx**: Latest (reverse proxy, static file serving)
- **Docker**: Latest
- **Docker Compose**: v2

### Deployment & Security
- **Azure VM**: Standard D2s_v3 (2 vCPU, 8GB RAM)
- **Cloudflare**: WAF, SSL termination, CDN
- **UFW**: Firewall (Cloudflare IPs only)
- **Caddy or Nginx**: Web server with Let's Encrypt fallback

### Monitoring & Logging
- **Structlog**: Structured logging
- **Sentry**: Error tracking (free tier)

## Implementation Phases

### Phase 1: Project Foundation
**Goal**: Set up monorepo structure, development environment, and CI/CD

1. **Monorepo Structure**
   - `/backend` - FastAPI application
   - `/frontend` - React + TypeScript + shadcn/ui
   - `/shared` - Shared types/schemas
   - `/docker` - Docker configurations
   - Root-level Docker Compose for local dev

2. **Backend Setup**
   - Python 3.14 with uv for package management
   - FastAPI with async support
   - SQLAlchemy ORM with async engine
   - Alembic for migrations
   - Pydantic v2 for data validation
   - Mypy strict mode configuration
   - Ruff for formatting/linting
   - Pytest + pytest-asyncio

3. **Frontend Setup**
   - Node.js 24 LTS
   - Vite 6 + React 19 + TypeScript 5.9
   - shadcn/ui (canary) + Tailwind CSS v4
   - React Router for navigation
   - Fetch API for backend calls
   - Full type safety

4. **Infrastructure**
   - Docker Compose: PostgreSQL 18, Redis 8.2.1, backend, frontend, Celery worker, Nginx
   - Environment configuration (.env.example)
   - GitHub Actions: lint, type-check, test on PRs
   - UFW firewall configuration script
   - Nginx reverse proxy configuration

### Phase 2: Database Models & Migrations

**Goal**: Define core data models

1. **User Model**
   - ID, auth0_id, created_at, updated_at
   - Email addresses (list, with verified flag)
   - Phone numbers (list, with verified flag)
   - Verification codes (separate table with expiry)

2. **TfL Data Models**
   - Station (id, name, lat/lon, lines)
   - Line (id, name, color, status)
   - StationConnection (from_station, to_station, line_id) - for route validation graph

3. **Route Models**
   - Route (user_id, name, active)
   - RouteSegment (route_id, sequence, station_id, line_id) - ordered list of stations/interchanges
   - RouteSchedule (route_id, days_of_week, start_time, end_time)

4. **Notification Models**
   - NotificationPreference (route_id, method: email/sms, target: specific email/phone)
   - NotificationLog (user_id, route_id, sent_at, method, status)

5. **Admin Models**
   - AdminUser (user_id, role)
   - Analytics events

6. **Database Security** (Deployment)
   - App container runs with limited DB user (SELECT, INSERT, UPDATE, DELETE only)
   - Migrations run separately in CI or init container with elevated privileges
   - Principle of least privilege - production app cannot ALTER tables or DROP database

### Phase 3: Auth0 Integration
**Goal**: Secure authentication with local testing

1. **Auth0 Setup**
   - Create Auth0 tenant
   - Configure application
   - Set up JWT verification in FastAPI
   - Password recovery via Auth0

2. **Testing Strategy**
   - Mock Auth0 JWT for local tests
   - Test user fixture
   - Environment flag to bypass Auth0 in dev

3. **APIs**
   - POST /auth/register - Create user record after Auth0 signup
   - GET /auth/me - Get current user profile
   - PUT /auth/profile - Update profile

### Phase 4: Contact Verification
**Goal**: Email and SMS verification with codes

1. **Verification Flow**
   - Generate 6-digit code, store with 15-min expiry
   - Email via SMTP (configurable provider)
   - SMS via Twilio stub (logs to console/file)

2. **APIs**
   - POST /contacts/email - Add email, send verification code
   - POST /contacts/phone - Add phone, send verification code
   - POST /contacts/verify - Verify code
   - DELETE /contacts/{id} - Remove contact
   - GET /contacts - List user contacts with verification status

### Phase 5: TfL Data Integration
**Goal**: Fetch and cache TfL station/line/disruption data

1. **Integration**
   - Use `pydantic_tfl_api` library
   - Async methods for all TfL API calls
   - Cache station/line data (refresh daily)
   - Cache disruption data (refresh every 2 minutes)

2. **Station Connection Graph**
   - Build graph from TfL station sequence data
   - Store in StationConnection table
   - Use for route validation (DFS/BFS to check valid path)

3. **APIs**
   - GET /tfl/lines - List all lines
   - GET /tfl/stations?line_id={id} - Stations on a line
   - GET /tfl/disruptions - Current disruptions
   - POST /tfl/validate-route - Validate station chain

### Phase 6: Route Management
**Goal**: Users can create and manage routes with interchanges

1. **Route Creation**
   - Accept start station, list of interchanges, end station
   - Validate each segment exists on a line (multi-line allowed)
   - Store as ordered RouteSegment records

2. **Schedule Configuration**
   - Multiple schedules per route
   - Days of week (bitmask or JSON array)
   - Start/end times

3. **APIs**
   - POST /routes - Create route
   - GET /routes - List user's routes
   - GET /routes/{id} - Get route details
   - PUT /routes/{id} - Update route
   - DELETE /routes/{id} - Delete route
   - POST /routes/{id}/schedule - Add schedule
   - PUT /routes/{id}/schedule/{schedule_id} - Update schedule

### Phase 7: Notification Preferences
**Goal**: Configure how and where alerts are sent per route

1. **Preference Management**
   - Link route to specific verified contact
   - Choose method (email or SMS)
   - Can have multiple preferences per route

2. **Validation**
   - Only allow verified contacts
   - Frontend shows verified status

3. **APIs**
   - POST /routes/{id}/notifications - Add notification preference
   - GET /routes/{id}/notifications - List preferences for route
   - DELETE /routes/{id}/notifications/{pref_id} - Remove preference

### Phase 8: Alert Processing Worker
**Goal**: Background worker to check disruptions and send alerts

1. **Celery Setup**
   - Celery with Redis broker
   - Beat scheduler for periodic tasks
   - Separate worker container

2. **Periodic Task** (every 5 minutes)
   - Fetch current disruptions from TfL
   - For each active route with current time in schedule:
     - Check if any disruption affects route stations/lines
     - If yes, check if alert already sent recently (deduplication)
     - Send notification via configured preferences
     - Log to NotificationLog

3. **Notification Sending**
   - Email: Use SMTP (async)
   - SMS: Twilio stub (log to file, prepare for future integration)
   - Dependency injection for testing

4. **Testing**
   - Mock TfL API responses
   - Mock email/SMS services
   - Test route matching logic
   - Test time-based filtering

### Phase 9: Admin Dashboard Backend
**Goal**: Admin APIs for user management and analytics

1. **Admin Authentication**
   - Admin role in database
   - Middleware to check admin status

2. **APIs**
   - GET /admin/users - List all users (paginated)
   - GET /admin/users/{id} - User details
   - DELETE /admin/users/{id} - Delete user
   - GET /admin/analytics/top-lines - Most affected lines
   - GET /admin/analytics/engagement - User engagement metrics
   - GET /admin/notifications - Recent notifications (paginated)

### Phase 10: Frontend Development

1. **Authentication Pages**
   - Login (redirect to Auth0)
   - Callback handler
   - Registration flow
   - Profile page

2. **Contact Management**
   - Add email/phone
   - Show verification status
   - Enter verification code modal
   - Remove contacts

3. **Route Builder** (most complex UI)
   - Search stations (autocomplete)
   - Add interchanges (dynamic list)
   - Visual route display (map or list)
   - Schedule configuration UI (day/time pickers)
   - Route validation feedback

4. **Notification Preferences**
   - Per-route notification setup
   - Select verified contacts
   - Choose method (email/SMS)
   - Enable/disable routes

5. **Admin Dashboard**
   - User list and management
   - Analytics charts (recharts or similar)
   - Notification logs

6. **Responsive Design**
   - Mobile-first approach
   - Material-UI responsive components
   - Test on various screen sizes

### Phase 11: Testing & Quality

1. **Backend Tests**
   - Unit tests for all services (>80% coverage)
   - Integration tests for APIs
   - Mock Auth0, TfL API, email/SMS
   - Test route validation logic thoroughly
   - Test alert matching and time filtering

2. **Frontend Tests**
   - Component tests (React Testing Library)
   - Integration tests for user flows
   - Mock API responses

3. **E2E Tests**
   - Critical user journeys
   - Playwright or Cypress
   - Auth flow, route creation, alert setup

### Phase 12: Deployment

1. **Azure VM Setup (Standard D2s_v3)**
   - Provision VM in Azure (2 vCPU, 8GB RAM)
   - Install Docker and Docker Compose
   - Configure UFW firewall (allow only Cloudflare IPs + SSH)
   - Set up automated backups for PostgreSQL data
   - Configure log rotation

2. **Cloudflare Configuration**
   - Point domain to Azure VM public IP
   - Enable WAF rules
   - Configure SSL/TLS (Full or Strict mode)
   - Set up CDN caching rules for static assets
   - Configure rate limiting

3. **Secret Management**
   - Install SOPS and age on VM
   - Generate age key pair (store private key on VM)
   - Create `.env.production.enc` encrypted with SOPS
   - Add decryption step to deployment script
   - Use Docker secrets for sensitive values in production

4. **Docker Compose Production Setup**
   - Production docker-compose.yml with:
     - PostgreSQL 18 with persistent volume
     - Redis 8.2.1
     - FastAPI backend with Gunicorn/Uvicorn
     - Celery worker with beat scheduler
     - Nginx reverse proxy (serves React static files, proxies API)
   - Health checks for all services
   - Resource limits (memory/CPU) per container
   - Restart policies

5. **Nginx Configuration**
   - Reverse proxy for FastAPI backend
   - Serve React static files
   - SSL termination (Let's Encrypt fallback if Cloudflare fails)
   - Gzip compression
   - Security headers

6. **CI/CD Pipeline (GitHub Actions)**
   - Run tests, linters, type checks on PR
   - Build Docker images on merge to main
   - Push images to GitHub Container Registry
   - SSH to Azure VM and deploy via docker-compose pull + restart
   - Run Alembic migrations before restarting services
   - Rollback on deployment failure

7. **UFW Firewall Rules**
   - Script to fetch Cloudflare IP ranges
   - Allow only Cloudflare IPs on ports 80/443
   - Allow SSH from specific IP or all (your choice)
   - Deny all other inbound traffic
   - Schedule weekly updates for Cloudflare IP list

8. **Monitoring & Observability**
   - Structlog for structured JSON logging
   - Sentry for error tracking (free tier)
   - Health check endpoints (/health, /ready)
   - Docker container health checks
   - Optional: Prometheus + Grafana for metrics (can add later)

9. **Backup Strategy**
   - Daily automated pg_dump to Azure Blob Storage
   - Retain 7 daily, 4 weekly backups
   - Test restore procedure
   - Backup Docker volumes

## Key Technical Considerations

### Route Validation Strategy
Use graph traversal (BFS) to validate routes:
1. Build station connection graph from TfL data
2. For each segment in route, check if path exists between stations on specified line
3. Validate interchanges have connections on both adjacent lines

### Alert Matching Logic
For each disruption:
1. Extract affected stations/lines
2. Query routes that include those stations/lines
3. Check route schedule against current time
4. Ensure no duplicate alert sent within last 2 hours
5. Send via user's configured preferences

### Testing Auth0 Locally
- Mock JWT validation in tests
- Use `pytest.fixture` with fake user
- Environment variable to disable Auth0 in dev mode
- Factory pattern for auth service (dependency injection)

### Cost Optimization
- Azure Standard D2s_v3 VM: ~$70/month (within $150 free credit)
- Leaves ~$80/month for:
  - Managed disks: ~$10/month for 128GB SSD
  - Data transfer: ~$5-10/month (Cloudflare reduces this significantly)
  - Blob storage for backups: ~$2-5/month
  - Total: ~$90-95/month (comfortably within budget)
- Cloudflare free tier: SSL, CDN, WAF, DDoS protection
- No separate database costs (self-hosted in Docker)
- Sentry free tier: 5k errors/month
- GitHub Actions: 2000 minutes/month free

## Tech Stack Summary
- **Backend**: Python 3.14, FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2, Celery 5.4
- **Frontend**: Node.js 24 LTS, React 19, TypeScript 5.9, Vite 6, shadcn/ui, Tailwind v4, React Router
- **Database**: PostgreSQL 18 (Docker)
- **Cache/Queue**: Redis 8.2.1 (Docker)
- **Auth**: Auth0 with local test mocks
- **Package Management**: uv (Python), npm/pnpm (Node)
- **Code Quality**: Mypy (strict), Ruff, ESLint, Prettier
- **Testing**: pytest + pytest-asyncio, React Testing Library, Playwright
- **CI/CD**: GitHub Actions + GitHub Container Registry
- **Deployment**: Azure VM (Standard D2s_v3) with Docker Compose
- **Security**: Cloudflare WAF + UFW firewall, SOPS/age for secrets
- **Monitoring**: Structlog, Sentry (free tier), Docker health checks
- **Web Server**: Nginx (reverse proxy + static files)

## Implementation Approach
Phased implementation allowing for incremental progress. Each phase can be completed independently before moving to the next.

## Next Steps (Phase 1 Start)

Once this plan is committed, Phase 1 implementation will begin with:

1. **Directory Structure Creation**
   ```
   IsTheTubeRunning/
   ├── backend/
   │   ├── app/
   │   │   ├── api/
   │   │   ├── core/
   │   │   ├── models/
   │   │   ├── services/
   │   │   └── main.py
   │   ├── tests/
   │   ├── alembic/
   │   ├── pyproject.toml
   │   └── Dockerfile
   ├── frontend/
   │   ├── src/
   │   │   ├── components/
   │   │   ├── pages/
   │   │   ├── lib/
   │   │   └── App.tsx
   │   ├── public/
   │   ├── package.json
   │   ├── tsconfig.json
   │   ├── vite.config.ts
   │   └── Dockerfile
   ├── docker/
   │   ├── nginx/
   │   │   └── nginx.conf
   │   └── scripts/
   │       ├── ufw-cloudflare.sh
   │       └── backup-db.sh
   ├── .github/
   │   └── workflows/
   │       ├── ci.yml
   │       └── deploy.yml
   ├── docker-compose.yml
   ├── docker-compose.prod.yml
   ├── .env.example
   ├── .env.production.enc (SOPS encrypted)
   ├── .gitignore
   └── README.md
   ```

2. **Configuration Files**
   - Python: pyproject.toml with uv, mypy.ini, ruff.toml
   - Node: package.json, tsconfig.json, vite.config.ts, tailwind.config.js
   - Docker: Dockerfiles for backend/frontend, docker-compose files
   - Git: .gitignore, .gitattributes
   - GitHub Actions: CI/CD workflows

3. **Development Environment**
   - Docker Compose for local dev (PostgreSQL, Redis, backend, frontend)
   - Hot reload for both backend and frontend
   - Shared network for services
   - Volume mounts for development

## Implementation Status

### Completed Phases
- [x] Planning and Architecture Design
- [x] Phase 1: Project Foundation (Completed: November 2025)
- [x] Phase 2: Database Models & Migrations (Completed: November 2025)
  - CI tests fixed with python-dotenv-vault secret management
  - Pre-commit hooks configured for automatic .env.vault rebuilding
- [x] Phase 3: Auth0 Integration (Completed: November 2025)
  - User model refactored: auth0_id → external_id + auth_provider for multi-provider support
  - Mock JWT generator using RS256 (production algorithm) with ephemeral RSA keys
  - Config validation utility (require_config()) for all modules
  - API security: UserResponse excludes external_id/auth_provider fields
  - All URLs constructed using urllib for proper escaping
  - Test fixtures use unique IDs to prevent collisions
  - Coverage: 96.37% (exceeds 95% target)
  - Alembic: Added clear feedback messages; startup validation in production mode

- [x] Phase 4: Contact Verification (Completed: November 2025)
  - Email/phone contact management with verification codes
  - HTML email templates with Jinja2
  - SMS stub service with console and file logging
  - Rate limiting: 3 verification codes per hour, 5 failed additions per 24h
  - Simple random 6-digit numeric codes (15-minute expiry)
  - Rate limit reset on successful verification
  - Coverage: 98.85% (exceeds 95% target) - 148 tests passing

### Upcoming Phases
- [ ] Phase 5: TfL Data Integration
- [ ] Phase 6: Route Management
- [ ] Phase 7: Notification Preferences
- [ ] Phase 8: Alert Processing Worker
- [ ] Phase 9: Admin Dashboard Backend
- [ ] Phase 10: Frontend Development
- [ ] Phase 11: Testing & Quality
- [ ] Phase 12: Deployment

## Notes and Decisions

### Key Architectural Decisions Made
1. **Monorepo**: Easier management for hobby project, shared types
2. **Auth0**: Offload auth complexity, focus on core features
3. **Multi-line routes**: More realistic commute scenarios
4. **Celery + Redis**: Proper async job handling for scalability
5. **Azure VM + Docker Compose**: Full control, cost-effective within free credits, no per-service pricing
6. **Cloudflare + UFW**: Free WAF, SSL, CDN; restrict access to Cloudflare IPs only
7. **SOPS/age + Docker secrets**: Self-contained secret management, no external service dependency
8. **shadcn/ui**: Lightweight, customizable, modern Tailwind-based components
9. **Code-based verification**: Consistent UX for email and SMS
10. **uv for Python**: Fast, modern package management
11. **Tailwind CSS v4**: Using latest v4 (not v3). Configuration and syntax differ significantly from v3. Use Context7 or WebFetch tools to get current v4 documentation when needed.
12. **UUIDs for Primary Keys**: Prevents enumeration attacks, better security for user data (Phase 2)
13. **Soft Deletes**: Audit trail and data recovery capability via deleted_at timestamp (Phase 2)
14. **JSON for Route Schedules**: PostgreSQL JSON support for days_of_week arrays (Phase 2)
15. **Required Config**: DATABASE_URL, REDIS_URL, ALLOWED_ORIGINS must be provided; no misleading defaults (Phase 2)
16. **DB Credential Separation**: App runs with limited DB permissions; migrations in separate CI/init container with admin access (Phase 2)
17. **python-dotenv-vault for Secrets**: Replaced SOPS/age with python-dotenv-vault for simpler encrypted secret management; locally managed (no cloud service), pre-commit hooks auto-rebuild .env.vault (Phase 2)
18. **Rate Limiting Strategy**: Two-tier rate limiting for security - verification codes (3/hour to prevent spam) and failed contact additions (5/24h to prevent enumeration attacks) (Phase 4)
19. **Simple Verification Codes**: Random 6-digit numeric codes instead of HOTP/TOTP for better email/SMS UX; industry standard for contact verification (Phase 4)
20. **Separate Verification Flow**: Users add contacts first, then explicitly request verification; provides better UX and allows batch contact addition (Phase 4)
21. **Test Database Setup**: pytest-postgresql automatically creates isolated test databases for each test with Alembic migrations. DO NOT manually create test databases or set DATABASE_URL in pytest commands - the test infrastructure handles this automatically via the `db_session` fixture in conftest.py (Phase 4)
22. **Test Authentication Pattern**: When testing authenticated endpoints, use `test_user` + `auth_headers_for_user` fixtures together. The `auth_headers_for_user` fixture generates a JWT token that matches the `test_user`'s external_id, ensuring test data and authenticated requests use the same user. DO NOT use `test_user` + `auth_headers` together as they create different users with mismatched external_ids (Phase 4)


### Future Enhancements (Post-MVP)
- SMS implementation via Twilio
- Mobile app (React Native)
- Push notifications
- Route suggestions based on user patterns
- Historical disruption analytics
- Integration with other transit systems

## Progress Tracking

This document will be updated as phases are completed. Each phase will be marked with completion status and any relevant notes about implementation decisions or deviations from the original plan.
