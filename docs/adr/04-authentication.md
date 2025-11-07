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
