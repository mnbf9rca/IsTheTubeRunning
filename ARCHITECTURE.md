# Architecture Decision Records (ADR)

This document captures key architectural decisions made during the development of the TfL Disruption Alert System.

**Note**: When running commands in `/backend`, ALWAYS use `uv run` (never naked `python`). Do not use `pip`.

---

## Table of Contents

1. [Project Structure & Infrastructure](#project-structure--infrastructure)
2. [Development Tools & Code Quality](#development-tools--code-quality)
3. [Database & Data Modeling](#database--data-modeling)
4. [Authentication & Authorization](#authentication--authorization)
5. [Security & Secrets Management](#security--secrets-management)
6. [Contact Verification & User Management](#contact-verification--user-management)
7. [External API Integration](#external-api-integration)
8. [Background Jobs & Workers](#background-jobs--workers)
9. [API Design](#api-design)
10. [Testing Strategy](#testing-strategy)

---

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

# Development Tools & Code Quality

## uv for Python Package Management

### Status
Active

### Context
Traditional Python package management with `pip` and `virtualenv` is slow and lacks modern features like lockfiles and dependency resolution. Need a faster, more reliable solution.

### Decision
Use `uv` for all Python package management. All backend commands must use `uv run` prefix. Never use naked `python` or `pip` commands.

### Consequences
**Easier:**
- Extremely fast package installation and resolution
- Built-in virtual environment management
- Lockfile support for reproducible builds
- Modern CLI similar to npm/pnpm
- Better dependency conflict resolution

**More Difficult:**
- Team members must install `uv` (additional setup step)
- Less familiar than `pip` (smaller community, fewer Stack Overflow answers)
- Must remember to prefix commands with `uv run`

---

## Tailwind CSS v4

### Status
Active

### Context
Need a modern, utility-first CSS framework for frontend. Tailwind CSS v4 introduces significant improvements over v3, including better performance and native CSS features.

### Decision
Use Tailwind CSS v4 (not v3). Configuration and syntax differ significantly from v3. Use Context7 or WebFetch tools to get current v4 documentation when needed.

### Consequences
**Easier:**
- Latest features and performance improvements
- Native CSS features (better browser support)
- Improved developer experience with v4 tooling
- Future-proof choice (v4 is current)

**More Difficult:**
- Limited online resources (many tutorials still use v3)
- Migration guides from v3 may not directly apply
- Need to reference v4-specific documentation
- Breaking changes from v3 if copying code snippets

---

## shadcn/ui Component Library

### Status
Active

### Context
Need a component library for React frontend that is lightweight, customizable, and doesn't bloat bundle size. Traditional component libraries like Material-UI are heavy and opinionated.

### Decision
Use shadcn/ui (canary version for React 19 support) - a collection of copy-paste components built on Radix UI primitives and styled with Tailwind CSS.

### Consequences
**Easier:**
- Full control over component code (components live in your codebase)
- Lightweight (only install components you use)
- Highly customizable (modify component code directly)
- Built on accessible Radix UI primitives
- No runtime dependency on a component library package

**More Difficult:**
- Components are copied into codebase (more files to maintain)
- Updates require manually copying new component versions
- No centralized component package updates
- Using canary version (less stable than production releases)

---

# Database & Data Modeling

## UUIDs for Primary Keys

### Status
Active

### Context
Sequential integer IDs are predictable and enable enumeration attacks where attackers can guess valid IDs to access resources. For user-facing data like routes and notifications, this is a security risk.

### Decision
Use UUIDs (UUID4) for all primary keys instead of auto-incrementing integers.

### Consequences
**Easier:**
- Prevents enumeration attacks (UUIDs are unpredictable)
- Better security for user data
- Distributed systems can generate IDs without coordination
- Can generate IDs client-side before database insert

**More Difficult:**
- Larger index size (16 bytes vs 4-8 bytes)
- Slightly slower lookups (though negligible with proper indexing)
- Less human-readable in logs and debugging
- URLs are longer (`/routes/550e8400-e29b-41d4-a716-446655440000` vs `/routes/123`)

---

## Soft Deletes

### Status
Active

### Context
Hard deletes permanently remove data, making audit trails impossible and preventing data recovery if deletion was accidental or malicious. GDPR compliance also requires ability to restore data in some cases.

### Decision
Implement soft deletes using `deleted_at` timestamp column. Records with `deleted_at != NULL` are considered deleted. Queries must filter by `deleted_at IS NULL` by default.

### Consequences
**Easier:**
- Audit trail of all deletions
- Data recovery possible (change `deleted_at` back to NULL)
- Compliance with data retention policies
- Analytics can include deleted records if needed

**More Difficult:**
- Must remember to filter by `deleted_at IS NULL` in all queries
- Database grows larger over time (deleted records remain)
- Need periodic cleanup jobs to permanently remove old soft-deleted records
- Unique constraints must account for soft-deleted records

---

## JSON for Route Schedules

### Status
Active

### Context
Route schedules need to store "days of week" (e.g., `["Mon", "Tue", "Wed"]`). Options include: separate `route_schedule_days` table with 7 potential rows per schedule, bitmask integer, or JSON array.

### Decision
Store `days_of_week` as JSON array in PostgreSQL. Example: `["Mon", "Tue", "Wed", "Fri"]`.

### Consequences
**Easier:**
- Single column stores entire days array
- Native PostgreSQL JSON support with indexing and querying
- Easy to add/remove days (update single field)
- Human-readable in database
- Validates easily with Pydantic

**More Difficult:**
- Cannot query "all schedules with Monday" without JSON query operators (acceptable tradeoff)
- JSON queries are less intuitive than SQL joins
- Slightly larger storage than bitmask (but more readable)

---

## Explicit Route Timezones

### Status
Active

### Context
Schedule times like "08:00 - 09:00" are ambiguous without timezone. During DST transitions, times can be interpreted incorrectly. System needs to support future expansion to cities outside London.

### Decision
Routes store explicit `timezone` field in IANA format (e.g., `"Europe/London"`). Schedule `start_time`/`end_time` remain timezone-naive (stored as `time` not `timestamptz`) and are interpreted in the route's timezone. DST is handled naturally by Python's `zoneinfo`.

### Consequences
**Easier:**
- Unambiguous schedule interpretation
- DST transitions handled automatically (no database updates needed)
- Portable design (supports future multi-city expansion)
- Type-safe (Pydantic validates IANA timezone names)
- Follows industry best practices

**More Difficult:**
- Must always interpret times in route's timezone (can't forget context)
- Slightly more complex queries (must join route to get timezone)
- Need to convert to user's timezone for display (but this is necessary anyway)

---

# Authentication & Authorization

## Auth0 for Identity Provider

### Status
Active

### Context
Implementing secure authentication from scratch is complex and error-prone. Need to handle OAuth flows, password reset, MFA, account recovery, and security best practices. This is undifferentiated heavy lifting for a hobby project.

### Decision
Use Auth0 as identity provider. Offload user registration, login, password management, and session handling to Auth0. Backend validates JWT tokens from Auth0.

### Consequences
**Easier:**
- No need to implement auth flows (login, registration, password reset)
- Battle-tested security (Auth0 handles tokens, sessions, MFA)
- Free tier sufficient for hobby project
- Focus development effort on core features
- Easy to add social logins later (Google, GitHub, etc.)

**More Difficult:**
- Dependency on external service (Auth0 outage affects login)
- Requires internet connection for auth (no offline capability)
- Must configure Auth0 tenant and keep config in sync
- Testing requires mocking Auth0 JWT validation

---

## Backend Auth as Single Source of Truth

### Status
Active

### Context
Frontend initially trusted Auth0's `isAuthenticated` state directly, allowing dashboard access even when backend was unavailable or returned 401/500 errors. This violated the principle that backend should be the authoritative source for authorization decisions.

### Decision
Frontend components use `isBackendAuthenticated` from `BackendAuthContext` instead of Auth0's `isAuthenticated` for all authorization decisions. Auth0 provides identity (who you are), backend provides authorization (what you can access). ProtectedRoute checks `isBackendAuthenticated` before rendering.

### Consequences
**Easier:**
- Frontend cannot access protected routes when backend validation fails
- Clear separation of concerns: Auth0 = identity, Backend = authorization
- Backend unavailability properly blocks access
- Consistent authorization state across frontend

**More Difficult:**
- Need to maintain both Auth0 state and backend auth state
- Slightly more complex state management in frontend
- Must ensure both states stay in sync during logout

---

## Admin Role-Based Authorization

### Status
Active

### Context
Certain endpoints (user management, analytics, manual alert triggers) should only be accessible to administrators. Need a simple but secure way to restrict access.

### Decision
Protect admin endpoints with `require_admin()` FastAPI dependency that checks `admin_users` table. Two-tier auth: (1) JWT validation (any authenticated user), (2) admin role check (403 if not admin). AdminUser model tracks `role` (admin/superadmin), `granted_at`, and `granted_by` for audit trail.

### Consequences
**Easier:**
- Simple, declarative endpoint protection (`Depends(require_admin)`)
- Clear audit trail of who has admin privileges and when
- Follows principle of least privilege
- Easy to add more roles later (superadmin, moderator, etc.)
- Database-backed (no hardcoded admin users)

**More Difficult:**
- Need to manually grant admin privileges to first user
- Admin table must be seeded in production
- No UI for granting admin roles (must use database or admin endpoint)

---

## Backend Availability First Pattern

### Status
Active

### Context
During Phase 10 PR2.5, discovered that frontend showed confusing UX when backend was unavailable but Auth0 authentication succeeded. Users appeared logged in but couldn't access any data, with no clear explanation.

### Decision
Frontend checks backend health (`GET /api/v1/auth/ready`) before attempting authentication. If backend is unavailable, show `ServiceUnavailable` page with auto-retry every 10s via `BackendAvailabilityContext`. Only proceed to Auth0 login flow once backend is confirmed available.

### Consequences
**Easier:**
- Clear distinction between "backend unavailable" and "backend denies auth"
- Users get clear feedback when backend is down
- Auto-retry provides seamless recovery when backend comes back
- Prevents confusing "authenticated but can't access anything" state

**More Difficult:**
- Additional health check endpoint to maintain
- Frontend depends on backend health check being fast and reliable
- More complex startup flow (check backend → Auth0 → backend validation)

---

## Explicit Backend Validation in Callback

### Status
Active

### Context
Auth0 callback handler initially relied on automatic `useEffect` validation, which led to infinite retry loops when validation failed. Error handling was unclear, and users got stuck on callback page.

### Decision
Auth0 callback handler explicitly calls `validateWithBackend()` and implements three-way error handling: (1) 401/403 → force Auth0 logout, (2) 500+ → show retry option, (3) network error → show retry option. No automatic retry loops.

### Consequences
**Easier:**
- Clear user feedback for different error scenarios
- No infinite retry loops (validation happens once per callback)
- Explicit error messages ("Authentication denied" vs "Server error")
- Users can manually retry or logout

**More Difficult:**
- More complex callback component (handles multiple error states)
- Must distinguish between different error types (401 vs 500 vs network)
- Need to test all three error paths

---

## Intent Preservation on Auth Redirect

### Status
Active

### Context
When users refresh a page or directly navigate to a protected route (e.g., `/dashboard/contacts`), they get redirected to `/login`. After authentication, they were always sent to `/dashboard` instead of their intended destination, requiring extra navigation.

### Decision
`ProtectedRoute` passes intended route via location state when redirecting to login (`state={{ from: location.pathname }}`). `Login` component restores intended route after successful authentication, falling back to `/dashboard` if no state exists.

### Consequences
**Easier:**
- Better UX - users return to the page they originally tried to access
- No extra navigation clicks after login
- Standard pattern used by many SPAs (React Router, Next.js)

**More Difficult:**
- Must pass location state correctly in all redirects
- Need to handle case where location state is missing (e.g., direct login)
- Slightly more complex routing logic

---

# Security & Secrets Management

## python-dotenv-vault for Secrets

### Status
Active (Superseded SOPS/age)

### Context
Originally chose SOPS/age for encrypted secret management, but configuration was complex and required managing age keys separately. Needed a simpler solution that integrates with the Python ecosystem and supports local encryption without cloud services.

### Decision
Use `python-dotenv-vault` for encrypted secret management. Secrets stored in `.env.vault` file (encrypted), decrypted at runtime. Pre-commit hooks auto-rebuild `.env.vault` when `.env` changes. No cloud service required (locally managed encryption key).

### Consequences
**Easier:**
- Simpler setup than SOPS/age (no separate key management)
- Integrates directly with Python ecosystem
- Pre-commit hooks ensure `.env.vault` stays in sync
- No cloud service dependency (offline capable)
- Standard `.env` file format (familiar to developers)

**More Difficult:**
- Encryption key must be managed separately (can't commit to git)
- If encryption key is lost, secrets must be regenerated
- Less mature than SOPS (smaller community)

---

## DB Credential Separation

### Status
Active

### Context
Application should run with minimal database permissions (principle of least privilege). If application is compromised, attacker shouldn't be able to drop tables or modify schema. However, migrations require elevated permissions.

### Decision
Application runs with limited database user (SELECT, INSERT, UPDATE, DELETE only). Migrations run in separate CI/init container with admin database access. Production app cannot ALTER tables or DROP database.

### Consequences
**Easier:**
- Principle of least privilege enforced
- Compromised application can't modify schema
- Clear separation of concerns (app vs migrations)
- Audit trail of schema changes (migrations only in CI)

**More Difficult:**
- Need two sets of database credentials (app user, admin user)
- CI must have access to admin credentials
- Cannot run migrations from running application (must restart or use separate job)

---

## Required Config Validation

### Status
Active

### Context
Applications with misleading defaults (e.g., `DATABASE_URL = "sqlite:///"`) can start successfully but fail silently or behave incorrectly. Better to fail fast with clear error messages.

### Decision
Critical configuration values (`DATABASE_URL`, `REDIS_URL`, `ALLOWED_ORIGINS`) must be explicitly provided - no defaults. Application uses `require_config()` utility to validate configuration on startup and fails with clear error message if required values are missing.

### Consequences
**Easier:**
- Fail fast with clear error messages
- No silent failures due to wrong configuration
- Developers immediately know what config is missing
- Prevents accidental use of wrong database (e.g., dev database in production)

**More Difficult:**
- Cannot start application without all required config (but this is desired behavior)
- Need to document all required environment variables
- More verbose `.env.example` file

---

## Rate Limiting Strategy

### Status
Active

### Context
Contact verification and addition endpoints are vulnerable to abuse: attackers could spam verification codes or enumerate valid emails/phones by observing response times or error messages.

### Decision
Implement two-tier rate limiting: (1) Verification codes: 3 per hour per user (prevents spam), (2) Failed contact additions: 5 per 24 hours per user (prevents enumeration attacks). Rate limits reset on successful verification. Store rate limit counters in Redis.

### Consequences
**Easier:**
- Prevents verification code spam
- Prevents enumeration attacks (can't rapidly test many contacts)
- Protects email/SMS providers from abuse
- Legitimate users unlikely to hit limits (3 codes/hour is generous)

**More Difficult:**
- Need to maintain rate limit state in Redis
- Edge cases to handle (what if Redis is down?)
- Users who genuinely need more codes must wait (but this is rare)

---

# Contact Verification & User Management

## Code-based Verification

### Status
Active

### Context
Email and SMS verification could use different mechanisms (email links vs SMS codes), but this creates inconsistent UX and more complex frontend logic.

### Decision
Use numeric verification codes for both email and SMS. Users enter 6-digit code in the same UI flow regardless of contact type.

### Consequences
**Easier:**
- Consistent UX for both email and SMS
- Single verification flow in frontend
- Same backend logic for both contact types
- Mobile-friendly (easy to type 6 digits)

**More Difficult:**
- Email links might be more familiar to some users
- Users must manually copy code from email (vs clicking link)

---

## Simple Verification Codes

### Status
Active

### Context
Could use HOTP/TOTP for verification codes (cryptographically secure), but these are overkill for contact verification and harder to implement. Industry standard for email/SMS verification is simple random codes.

### Decision
Generate random 6-digit numeric codes for verification. 15-minute expiry. Industry standard for contact verification.

### Consequences
**Easier:**
- Simple to implement (no HOTP/TOTP library needed)
- Easy to type (6 digits)
- Industry standard (users are familiar)
- Good enough security with rate limiting

**More Difficult:**
- Not cryptographically secure (but acceptable for contact verification)
- Could theoretically brute force (but rate limiting prevents this)

---

## Separate Verification Flow

### Status
Active

### Context
Could auto-send verification code immediately when contact is added, but this prevents users from adding multiple contacts before verifying. Also, users might want to add a contact but verify it later.

### Decision
Users add contacts first (returns unverified contact), then explicitly request verification code via separate API call. Allows batch contact addition before verification.

### Consequences
**Easier:**
- Better UX (add multiple contacts, then verify in batch)
- Users control when codes are sent (not automatic)
- Clearer separation of "add" vs "verify" actions
- Can re-send verification code without re-adding contact

**More Difficult:**
- Two-step process instead of one
- More API calls (add contact, then verify)
- Need to track verification state per contact

---

## Privacy-Focused User Deletion

### Status
Active

### Context
GDPR and privacy regulations require ability to delete user data. However, hard deletes make analytics impossible. Need balance between privacy and analytics.

### Decision
`DELETE /admin/users/{id}` implements GDPR-style data minimization while preserving analytics. Deletes PII (email_addresses, phone_numbers, verification_codes), anonymizes `external_id` to `"deleted_{user_id}"`, clears `auth_provider`, deactivates all routes (stops alerts), sets `deleted_at` timestamp. Preserves `notification_logs` and route structure for aggregated analytics (user_id becomes anonymous identifier). Transaction-based to ensure atomicity.

### Consequences
**Easier:**
- GDPR compliant (PII is deleted)
- Analytics still possible (aggregated metrics work)
- Audit trail preserved (`deleted_at` timestamp)
- Atomic operation (transaction ensures all-or-nothing)

**More Difficult:**
- More complex deletion logic (multiple tables, specific order)
- Anonymized users remain in database (soft delete)
- Must distinguish "deleted user" from "active user" in queries
- Cannot fully purge user (some records remain for analytics)

---

## Explicit NotificationPreference Deletion on Anonymization

### Status
Active

### Context
When anonymizing users, notification preferences could be preserved (they link to routes), but these preferences are meaningless without active contacts. Could rely on CASCADE DELETE, but this makes deletion implicit and harder to understand.

### Decision
Explicitly delete `NotificationPreference` records during user anonymization instead of relying on implicit CASCADE behavior.

### Consequences
**Easier:**
- Code clarity - deletion is explicit for future maintainers
- KISS/YAGNI - no need for placeholder contacts or schema changes
- Data minimization - preference configurations (intent) without active users are not actionable
- Analytics sufficiency - `NotificationLog` preserves actual behavior data (what was sent, success rates)

**More Difficult:**
- Must remember to delete preferences explicitly (can't rely on CASCADE)
- More lines of code in deletion logic

---

# External API Integration

## pydantic-tfl-api Integration

### Status
Active

### Context
The `pydantic-tfl-api` library provides type-safe TfL API client with Pydantic models, but it's synchronous. Our FastAPI backend is async. Need to integrate synchronous library into async codebase.

### Decision
Wrap all TfL API calls in `asyncio.get_running_loop().run_in_executor()` to maintain async compatibility. Client initialization uses optional `app_key` parameter (for rate limit increase). Responses are either `ApiError` or success objects with `.content` attribute containing Pydantic models.

### Consequences
**Easier:**
- Type-safe API responses (Pydantic models)
- Maintained library (don't need to write TfL client from scratch)
- Maintains async compatibility in FastAPI

**More Difficult:**
- Wrapper boilerplate for every TfL API call
- Executor runs in thread pool (slight overhead)
- Testing requires mocking `asyncio.get_running_loop()`

---

## Dynamic Cache TTL

### Status
Active

### Context
TfL API returns `content_expires` field indicating when data should be refreshed. Hardcoded cache TTLs can lead to stale data or unnecessary API calls.

### Decision
Extract cache TTL from TfL API `content_expires` field rather than using hardcoded values. Falls back to sensible defaults (24h for lines/stations, 2min for disruptions) when TfL doesn't provide expiry.

### Consequences
**Easier:**
- Cache invalidation aligns with TfL's data freshness
- Respects TfL's caching guidance
- Automatic adjustment if TfL changes expiry times

**More Difficult:**
- Must parse `content_expires` field from every response
- Need fallback logic when field is missing
- Cache behavior depends on TfL's headers (less predictable)

---

## Simplified Station Graph

### Status
Active

### Context
Route validation requires knowing which stations connect to which on each line. TfL API provides station sequences per line. Could build complex graph with all connections or simplified version.

### Decision
Build simplified bidirectional graph: create edges between consecutive stations on each line as returned by TfL API. Suitable for basic route validation; actual route sequences would provide more accuracy but require more complex TfL API integration.

### Consequences
**Easier:**
- Simple graph building logic (consecutive stations → edge)
- Fast route validation (BFS/DFS)
- Sufficient for MVP use case

**More Difficult:**
- Not 100% accurate (may allow routes that aren't actually valid)
- Doesn't account for complex interchange rules
- May need to rebuild if accuracy becomes critical

---

## Admin Endpoint for Graph Building

### Status
Active

### Context
Station graph building requires fetching all TfL lines and stations, then processing connections. This takes several seconds. Running on startup would block application initialization.

### Decision
Station graph is built on-demand via admin endpoint (`POST /admin/tfl/build-graph`) rather than on startup. Can be automated with Celery scheduler in Phase 8.

### Consequences
**Easier:**
- Application starts immediately (no blocking startup tasks)
- Graph building can be triggered manually when needed
- Failures don't prevent application startup
- Can rebuild graph without restarting application

**More Difficult:**
- Must remember to build graph after deployment
- Route validation fails if graph hasn't been built
- Need to document graph building step in deployment docs

---

## Multi-line Routes

### Status
Active

### Context
Real commutes often involve multiple tube lines with interchanges (e.g., Northern Line → Victoria Line → Central Line). Supporting only single-line routes would be unrealistic.

### Decision
Routes support multiple segments, each on a different line. Segments are ordered and validated to ensure consecutive segments connect via valid interchanges.

### Consequences
**Easier:**
- Realistic commute scenarios
- More useful for users (matches real-world travel)
- Better alert matching (disruption on any line in route triggers alert)

**More Difficult:**
- Complex route validation (must check each segment and interchange)
- More complex route builder UI (add/remove segments)
- Database schema includes route segments table

---

# Background Jobs & Workers

## Celery + Redis

### Status
Active

### Context
Alert processing (checking TfL disruptions and sending notifications) must run in background on schedule. Need reliable, scalable job queue.

### Decision
Use Celery with Redis broker. Celery Beat for scheduled tasks (every 30s). Separate worker container from FastAPI app.

### Consequences
**Easier:**
- Proper async job handling (non-blocking)
- Scalable (can add more workers)
- Reliable (Redis ensures task durability)
- Industry standard (well-documented)
- Scheduled tasks built-in (Celery Beat)

**More Difficult:**
- Additional infrastructure (Redis, Celery worker container)
- More complex monitoring (need to monitor worker health)
- Debugging can be harder (tasks run in separate process)

---

## Content-Based Alert Deduplication

### Status
Active

### Context
Disruptions can persist for hours or days. Sending the same alert repeatedly would spam users. But if disruption status changes (e.g., "minor delays" → "severe delays"), users should be notified.

### Decision
Track last alert state in Redis (key: `last_alert:{route_id}:{user_id}`) with SHA256 hash of disruption details (line_id, status_severity_description, reason). Only send new alert if content changed. TTL: 7 days for auto-cleanup.

### Consequences
**Easier:**
- Prevents alert spam (same disruption = no new alert)
- Users informed of status changes (content hash changes = new alert)
- Fast lookups (Redis key-value)
- Automatic cleanup (7-day TTL)

**More Difficult:**
- Depends on Redis for state (if Redis is flushed, may re-send alerts)
- Need to serialize disruption details consistently for hashing
- Status changes that don't change hash won't trigger new alert

---

## Hybrid Task Scheduling

### Status
Active

### Context
Want to check for disruptions frequently (responsive alerts) but don't want to spam TfL API. TfL data is cached with 2-minute TTL.

### Decision
Celery Beat runs disruption check task every 30 seconds, but TfL data fetch respects cache layer TTL (typically 2 minutes). Task timeout: 5 min hard limit, 4 min soft limit to prevent runaway tasks.

### Consequences
**Easier:**
- Dynamic scheduling without complex logic
- Responsive to cache expiry (checks when cache is likely stale)
- Minimizes redundant API calls (cache layer prevents excess calls)
- Fast response to disruptions (30s granularity)

**More Difficult:**
- Task scheduling depends on cache behavior (less explicit)
- Must ensure cache TTL is reasonable (too long = stale data)

---

## Worker Database Sessions

### Status
Active

### Context
Celery workers need database access but share the same database as FastAPI app. Connection pool conflicts can occur if both use the same engine.

### Decision
Celery workers use separate async SQLAlchemy engine/session factory from FastAPI app. Uses NullPool in tests for isolation, QueuePool in production for connection reuse. Workers get sessions via `get_worker_session()` helper with proper cleanup.

### Consequences
**Easier:**
- Prevents connection pool conflicts
- Workers and app can scale independently
- Clear separation of concerns
- Proper connection cleanup in workers

**More Difficult:**
- Must maintain two database engines (app, worker)
- More complex configuration
- Need to ensure both engines use correct pool settings

---

# API Design

## KISS Analytics Approach

### Status
Active

### Context
Admin dashboard needs user counts, route stats, notification stats, and growth metrics. Could create multiple specialized endpoints or single comprehensive endpoint.

### Decision
Single comprehensive engagement endpoint (`GET /admin/analytics/engagement`) instead of multiple specialized analytics APIs. Returns four metric categories in one call: user counts, route stats, notification stats, growth/retention metrics. Can add specialized endpoints later if needed.

### Consequences
**Easier:**
- Reduces API surface area
- Simplifies frontend integration (one API call)
- Follows YAGNI principle (don't build what we don't need yet)
- Easier to add specialized endpoints later if traffic becomes concern

**More Difficult:**
- Single endpoint returns more data than needed if only one metric is desired
- Cannot cache individual metrics separately (cache whole response or nothing)
- Larger response payload

---

# Testing Strategy

## Test Database Setup

### Status
Active

### Context
Each test needs isolated database to prevent test pollution. Manually creating databases or setting `DATABASE_URL` is error-prone and requires coordination.

### Decision
`pytest-postgresql` automatically creates isolated test databases for each test with Alembic migrations. DO NOT manually create test databases or set `DATABASE_URL` in pytest commands - the test infrastructure handles this automatically via the `db_session` fixture in `conftest.py`.

### Consequences
**Easier:**
- Automatic test database creation (no manual setup)
- Isolated tests (no shared state between tests)
- Migrations run automatically (database schema matches application)
- Fast test execution (each test uses fresh database)

**More Difficult:**
- Must use `db_session` fixture correctly
- Cannot connect to test database manually (it's ephemeral)
- Debugging database state requires print statements or breakpoints

---

## Test Authentication Pattern

### Status
Active

### Context
Testing authenticated endpoints requires generating JWT tokens that match test users. Mismatched `external_id` between user and token causes 403 errors.

### Decision
When testing authenticated endpoints, use `test_user` + `auth_headers_for_user` fixtures together. The `auth_headers_for_user` fixture generates a JWT token that matches the `test_user`'s `external_id`, ensuring test data and authenticated requests use the same user. DO NOT use `test_user` + `auth_headers` together as they create different users with mismatched `external_id`s.

### Consequences
**Easier:**
- Correct fixture pairing ensures tests pass
- Clear pattern to follow (`test_user` + `auth_headers_for_user`)
- Matches production behavior (token `external_id` matches user)

**More Difficult:**
- Must remember correct fixture pairing (documentation helps)
- Two separate fixtures (`auth_headers` vs `auth_headers_for_user`) can be confusing

---

## NullPool for Async Test Isolation

### Status
Active

### Context
Async SQLAlchemy tests with pytest-asyncio fail with "Task attached to a different loop" errors when using standard connection pooling. This occurs because pytest-asyncio creates new event loops per test, but pooled connections are tied to the original loop.

### Decision
Use `sqlalchemy.pool.NullPool` for database connections in test environments (`app/core/database.py` when `DEBUG=true`, `tests/conftest.py` for test fixtures). Each database operation creates a fresh connection instead of pooling.

### Consequences
**Easier:**
- No event loop errors in async tests
- Standard solution for async SQLAlchemy testing
- Simple configuration change (pool_class=NullPool)

**More Difficult:**
- Slightly slower tests (no connection reuse)
- Must remember to use NullPool in tests (but configured automatically)

---

## Async Test Mocking Strategy

### Status
Active

### Context
Testing TfL service requires mocking synchronous library calls wrapped in `run_in_executor()`. Could mock client classes or mock executor directly.

### Decision
Mock `asyncio.get_running_loop()` directly instead of mocking client classes in TfL service tests. Pattern: `mock_loop = AsyncMock(); mock_loop.run_in_executor = AsyncMock(return_value=mock_response); mock_get_loop.return_value = mock_loop`

### Consequences
**Easier:**
- Simpler mocking (mock executor, not client)
- More explicit about async behavior
- Avoids freezegun async complications
- Works with any synchronous library (not specific to pydantic-tfl-api)

**More Difficult:**
- Less intuitive than mocking client classes
- Must mock loop for every test
- Pattern is not obvious to developers unfamiliar with run_in_executor

---

## Test Database Dependency Override Pattern

### Status
Active

### Context
Integration tests using `AsyncClient` with `ASGITransport(app=app)` need to use test database instead of production database URL from settings. Without override, tests fail with "relation does not exist" errors.

### Decision
When creating fixtures that use `AsyncClient` with `ASGITransport(app=app)`, MUST override `app.dependency_overrides[get_db]` to use the test `db_session` fixture. Pattern: Import `get_db` from `app.core.database`, create override function `async def override_get_db() -> AsyncGenerator[AsyncSession]: yield db_session`, set `app.dependency_overrides[get_db] = override_get_db`, use try/finally to clear overrides.

### Consequences
**Easier:**
- Tests use correct database (test database with migrations)
- Clear error messages when override is missing
- Standard pattern for FastAPI testing

**More Difficult:**
- Must remember to add dependency override in fixtures
- Boilerplate code in each fixture
- Easy to forget try/finally cleanup

---

## IntegrityError Recovery Test Pattern

### Status
Active

### Context
Testing error recovery code (catching `IntegrityError`, rolling back, continuing with queries) requires REAL database commits. Standard `db_session` fixture uses SAVEPOINT transactions, which don't accurately test recovery because: (1) sync listener conflicts with async rollback, (2) rollback would erase all test data.

### Decision
Use `fresh_db_session` fixture which creates a new database per test with Alembic migrations. This is slower (~2s vs ~0.1s) but supports testing real-world error recovery code paths. Currently used by 5 tests: race condition handling in user creation, duplicate email/phone detection with different casing/formatting. The `fresh_async_client` fixture pairs with `fresh_db_session` for API testing.

### Consequences
**Easier:**
- Can test REAL error recovery (IntegrityError handling)
- Matches production behavior exactly
- No sync/async conflicts with rollback

**More Difficult:**
- Much slower tests (~2s per test vs ~0.1s)
- Should only be used when necessary (not for all tests)
- Need separate fixture (`fresh_db_session` vs `db_session`)

---

# How to Add New Architecture Decisions

When making a significant architectural decision, add it to this document using the following process:

1. **Choose the correct section** - Add your decision to the most appropriate logical grouping above, or create a new section if needed.

2. **Use the ADR template** - Format your decision as follows:

```markdown
## [Decision Title]

### Status
[Active | Deprecated | Superseded by [Decision Title]]

### Context
[What is the issue that we're seeing that is motivating this decision or change?]

### Decision
[What is the change that we're proposing and/or doing?]

### Consequences
**Easier:**
- [What becomes easier because of this decision?]
- [List multiple benefits]

**More Difficult:**
- [What becomes more difficult because of this decision?]
- [List tradeoffs and limitations]
```

3. **Be specific** - Include concrete examples, code patterns, or file references where relevant.

4. **Consider both sides** - Always document both benefits (easier) and tradeoffs (more difficult). Every architectural decision has tradeoffs.

5. **Update status when superseded** - If a decision is replaced by a newer one, update its status to "Superseded by [New Decision Title]" rather than deleting it. This preserves historical context.

6. **Keep it concise** - ADRs should be scannable. Link to external docs for detailed implementation guides if needed.

7. **Review before merging** - Architectural decisions affect the entire team and future maintainers. Get review before merging significant changes to this document.
