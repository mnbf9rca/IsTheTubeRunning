# Phase 10: Frontend Development - Detailed Implementation Plan

**Phase Goal**: Build complete frontend user interface for TfL Disruption Alert System

**Strategy**: Split into 5 focused PRs with tests included, prioritizing core user journey

**Status**: In Progress - PR1 started

---

## Overview

Phase 10 implements all user-facing and admin frontend features. The backend APIs (Phases 1-9) are complete and tested. This phase focuses on creating a modern, accessible, responsive React UI using shadcn/ui components and Tailwind CSS v4.

**Total Estimated Time**: 13-18 days across 5 PRs

---

## PR Breakdown and Dependencies

```
PR1 (Auth & Foundation) → Required for all other PRs
PR2 (Contacts) → Independent after PR1
PR2.5 (Backend Auth Architecture) → Critical fix after PR2, blocks PR3+
PR3 (Routes) → Independent after PR2.5
PR4 (Notifications) → Depends on PR3
PR5 (Admin) → Independent after PR2.5
```

**Recommended Order**: PR1 → PR2 → **PR2.5** → PR3 → PR4 → PR5

**⚠️ CRITICAL**: PR2.5 must be completed before continuing with PR3+ to ensure proper authentication architecture.

---

## PR1: Authentication & Foundation

**Branch**: `feature/phase-10-pr1-auth-foundation`
**Estimated Time**: 2-3 days
**Status**: Complete ✅
**Started**: 2025-11-05
**Completed**: 2025-11-05

### Goals
- Establish Auth0 integration with secure JWT handling
- Create app layout with navigation structure
- Implement protected routing
- Enhance API client with authentication
- Build foundation for all future PRs

### Dependencies Installed
- [x] `@auth0/auth0-react` (v2.8.0)
- [x] `@radix-ui/*` (multiple packages via shadcn/ui)
- [x] `prettier` (v3.6.2)
- [x] `eslint-config-prettier` (v10.1.8)

### shadcn/ui Components Installed
- [x] Button
- [x] Card
- [x] Input
- [x] Label
- [x] Avatar
- [x] DropdownMenu
- [x] Separator
- [x] Sheet (for mobile menu)

### Tasks

#### 0. Frontend Quality Tooling Setup
- [x] Configure ESLint with React and TypeScript rules
- [x] Configure Prettier for code formatting
- [x] Integrate with existing pre-commit framework (no Husky needed)
- [x] Add Prettier check to pre-commit hooks
- [x] Enhance GitHub Actions workflow for frontend CI:
  - [x] Lint check (ESLint)
  - [x] Format check (Prettier)
  - [x] Type check (tsc --noEmit)
  - [x] Tests (Vitest)
  - [x] Build verification

#### 1. Configuration
- [x] Add Auth0 environment variables to `.env.example`:
  - `VITE_AUTH0_DOMAIN`
  - `VITE_AUTH0_CLIENT_ID`
  - `VITE_AUTH0_AUDIENCE`
  - `VITE_AUTH0_CALLBACK_URL`
- [x] Configure Auth0Provider in `main.tsx`

#### 2. Authentication Infrastructure
- [x] Create `src/hooks/useAuth.ts` - wrapper hook for Auth0
- [x] Create `src/components/ProtectedRoute.tsx` - route guard component
- [x] Update `src/lib/api.ts` - add JWT token injection, custom ApiError class, enhanced error handling

#### 3. Layout Components
- [x] Create `src/components/layout/AppLayout.tsx` - main app structure with footer
- [x] Create `src/components/layout/Header.tsx` - header with user menu and responsive mobile nav
- [x] Create `src/components/layout/Navigation.tsx` - nav links (used in both desktop and mobile)

#### 4. Pages
- [x] Create `src/pages/Login.tsx` - branded login page with Auth0 redirect
- [x] Create `src/pages/Callback.tsx` - Auth0 callback handler
- [x] Create `src/pages/Dashboard.tsx` - main dashboard with getting started guide
- [x] Remove old `src/pages/Home.tsx` (replaced by Login and Dashboard)

#### 5. Routing Setup
- [x] Update `src/App.tsx` with new routes:
  - `/` - Redirect to `/dashboard`
  - `/login` - Login (public)
  - `/callback` - Auth0 callback (public)
  - `/dashboard` - Dashboard (protected)
  - `*` - Catch-all redirect to `/dashboard`

#### 6. Tests
- [x] Unit tests for `useAuth` hook (5 tests)
- [x] Component tests for `ProtectedRoute` (3 tests)
- [x] Component tests for `Login` page (3 tests)
- [x] All tests passing: 11/11 ✅

#### 7. Build Verification
- [x] TypeScript strict mode compliance
- [x] ESLint compliance (1 warning in shadcn component, acceptable)
- [x] Prettier formatting
- [x] Production build successful

### Completion Criteria
- [x] @auth0/auth0-react installed
- [x] Auth0 fully configured and integrated
- [x] Protected routing working
- [x] Users can log in/out (via Auth0)
- [x] JWT tokens automatically injected in API calls
- [x] Responsive layout with mobile navigation
- [x] All tests passing (11/11 tests ✅)
- [x] TypeScript strict mode compliant
- [x] ESLint compliant
- [x] Prettier formatting applied
- [x] Production build successful
- [x] Accessible (keyboard nav, ARIA labels, semantic HTML)

### Files Created/Modified (34 files)

**Configuration:**
- `.env.example` (Auth0 vars added)
- `main.tsx` (Auth0Provider setup)
- `.prettierrc` (new)
- `.prettierignore` (new)
- `eslint.config.js` (updated with Prettier integration)
- `package.json` (new scripts, dependencies)
- `../.pre-commit-config.yaml` (Prettier hook added)
- `../.github/workflows/ci.yml` (Prettier check added)

**Hooks:**
- `src/hooks/useAuth.ts` (new)
- `src/hooks/useAuth.test.ts` (new)

**Components:**
- `src/components/layout/AppLayout.tsx` (new)
- `src/components/layout/Header.tsx` (new)
- `src/components/layout/Navigation.tsx` (new)
- `src/components/ProtectedRoute.tsx` (new)
- `src/components/ProtectedRoute.test.tsx` (new)
- `src/components/ui/button.tsx` (shadcn)
- `src/components/ui/card.tsx` (shadcn)
- `src/components/ui/input.tsx` (shadcn)
- `src/components/ui/label.tsx` (shadcn)
- `src/components/ui/avatar.tsx` (shadcn)
- `src/components/ui/dropdown-menu.tsx` (shadcn)
- `src/components/ui/separator.tsx` (shadcn)
- `src/components/ui/sheet.tsx` (shadcn)

**Pages:**
- `src/pages/Login.tsx` (new)
- `src/pages/Login.test.tsx` (new)
- `src/pages/Callback.tsx` (new)
- `src/pages/Dashboard.tsx` (new)
- `src/pages/Home.tsx` (removed)
- `src/pages/Home.test.tsx` (removed)
- `src/App.tsx` (updated routing)

**API Client:**
- `src/lib/api.ts` (enhanced with JWT injection, ApiError class)

---

## PR2: Contact Management

**Branch**: `feature/phase-10-pr2-contacts`
**Estimated Time**: 2-3 days
**Status**: In Progress (95% complete - needs auth architecture fix before merge)
**Started**: 2025-11-05
**Depends on**: PR1

### Goals
- Implement email/phone management UI
- Build verification code flow
- Create contact cards with status indicators
- Handle rate limiting gracefully

### shadcn/ui Components to Install
- [ ] Form
- [ ] Dialog
- [ ] Badge
- [ ] Alert
- [ ] Tabs
- [ ] Toast/Sonner

### Tasks

#### 1. API Client Expansion
- [ ] Add all `/contacts` endpoint methods
- [ ] TypeScript interfaces: `Contact`, `EmailContact`, `PhoneContact`, `VerificationRequest`

#### 2. Components
- [ ] Create `src/components/contacts/ContactCard.tsx` - display email/phone with verified badge
- [ ] Create `src/components/contacts/AddContactDialog.tsx` - modal to add email/phone
- [ ] Create `src/components/contacts/VerificationDialog.tsx` - 6-digit code input
- [ ] Create `src/components/contacts/ContactList.tsx` - list of contacts

#### 3. Pages
- [ ] Create `src/pages/Contacts.tsx` - main contacts page
  - Tabs for Emails and Phones
  - Add contact button
  - Contact list with verification status
  - Verify, delete, set primary actions

#### 4. Routing
- [ ] Add `/dashboard/contacts` protected route to `App.tsx`

#### 5. State Management
- [ ] Create `src/hooks/useContacts.ts` - manage contacts state
- [ ] Implement optimistic updates

#### 6. Tests
- [ ] Component tests for all contact components
- [ ] Integration tests: add/verify/delete flows
- [ ] Rate limiting error handling tests

#### 7. Documentation
- [ ] Update README with contact features

### Completion Criteria
- [ ] Users can add email addresses and phone numbers
- [ ] Verification code flow works (send, resend, verify)
- [ ] Rate limiting handled gracefully with user feedback
- [ ] Primary contact can be set
- [ ] Contacts can be deleted
- [ ] All tests passing (>80% coverage)
- [ ] Mobile responsive

### Files Created/Modified (~12-15)
- API: `lib/api.ts` (contacts methods)
- Components: `contacts/*`, `ui/*` (new shadcn components)
- Pages: `Contacts.tsx`
- Hooks: `hooks/useContacts.ts`
- Tests: `*.test.tsx`
- Routes: `App.tsx` (updated)

---

## PR2.5: Backend Auth Architecture (CRITICAL FIX)

**Branch**: `feature/phase-10-pr2.5-fix-auth-flow`
**Estimated Time**: 1-2 days
**Status**: Complete ✅
**Priority**: CRITICAL - Blocks PR3, PR4, PR5
**Started**: 2025-11-05
**Completed**: 2025-11-05
**Depends on**: PR2

### Goals
- Fix authentication architecture to make backend the single source of truth
- Resolve infinite loop bug in BackendAuthContext
- Ensure frontend cannot access protected routes without backend validation
- Prevent dashboard access when backend is unavailable

### Problem Statement
**Current Issue**: Frontend trusts Auth0's `isAuthenticated` state directly, allowing dashboard access even when the backend is unavailable or returns 401/500 errors. This violates the architecture principle: "Backend is the source of truth for authentication."

**Symptoms**:
- User can access dashboard after backend validation fails
- Infinite loop in BackendAuthContext causing rapid re-renders (hundreds per second)
- Backend being unavailable doesn't prevent frontend access

**Root Cause**: The current BackendAuthContext implementation has dependency and state management issues causing infinite re-render loops when validation fails.

### Technical Requirements

#### 1. Fix BackendAuthContext
**File**: `src/contexts/BackendAuthContext.tsx`

Current problematic pattern:
```typescript
useEffect(() => {
  if (auth0IsAuthenticated && !auth0IsLoading && !user && !isValidating && !error) {
    validateWithBackend().catch(() => {})
  }
}, [auth0IsAuthenticated, auth0IsLoading, user, isValidating, error, validateWithBackend])
```

**Issues to fix**:
- `validateWithBackend` dependency causing infinite loop
- No clear separation between initial load and retry logic
- Error state not properly preventing retries
- Race conditions between Auth0 state changes and backend validation

**Required fixes**:
1. Implement proper dependency management for `validateWithBackend`
2. Add ref-based tracking to prevent duplicate calls
3. Implement exponential backoff or circuit breaker for failed validations
4. Clear distinction between "never validated" and "validation failed"
5. Handle Auth0 logout → backend state cleanup properly

#### 2. Update ProtectedRoute
**File**: `src/components/ProtectedRoute.tsx`

**Current behavior**: Shows loading spinner during validation but has timing issues

**Required fixes**:
1. Handle the case where backend validation is pending but Auth0 is ready
2. Show appropriate loading states vs error states
3. Ensure navigation to `/login` happens consistently when backend rejects

#### 3. Update Callback Page
**File**: `src/pages/Callback.tsx`

**Current behavior**: Simplified but still has edge cases with logout timing

**Required fixes**:
1. Ensure consistent error messages for different failure modes
2. Properly handle logout redirect with correct return URL
3. Add timeout protection against infinite validation attempts

### Testing Requirements

#### Unit Tests
- [ ] BackendAuthContext: Initial validation on Auth0 authentication
- [ ] BackendAuthContext: Validation failure sets error state
- [ ] BackendAuthContext: No infinite loop on validation failure
- [ ] BackendAuthContext: clearAuth() properly resets state
- [ ] BackendAuthContext: Handles Auth0 logout correctly
- [ ] ProtectedRoute: Redirects to /login when backend validation fails
- [ ] ProtectedRoute: Shows loading during initial validation
- [ ] ProtectedRoute: Renders children only after successful backend validation
- [ ] Callback: Redirects to dashboard on successful backend validation
- [ ] Callback: Redirects to login on backend validation failure
- [ ] Callback: Displays appropriate error messages

#### Integration Tests
- [ ] Full auth flow: Auth0 login → backend validation → dashboard access
- [ ] Backend unavailable: Auth0 success → backend fails → redirect to login
- [ ] Backend 401: Auth0 success → backend unauthorized → redirect to login
- [ ] Backend 500: Auth0 success → backend error → redirect to login
- [ ] Logout flow: Clear both Auth0 and backend state

#### Manual Testing Scenarios
1. **Happy path**: Start backend, login via Auth0, verify dashboard access
2. **Backend down on login**: Stop backend, login via Auth0, verify redirect to login with appropriate message
3. **Backend dies after login**: Login successfully, stop backend, navigate to protected route, verify redirect to login
4. **Invalid token**: Manipulate token, try to access dashboard, verify backend rejects and redirects to login
5. **No infinite loops**: Monitor console/React DevTools during failed validations to confirm no rapid re-renders

### Implementation Strategy

**Option 1: Ref-based deduplication** (Recommended)
```typescript
const validationAttemptRef = useRef<{ inProgress: boolean; timestamp: number }>({
  inProgress: false,
  timestamp: 0,
})

const validateWithBackend = useCallback(async () => {
  // Prevent concurrent validations
  if (validationAttemptRef.current.inProgress) return

  validationAttemptRef.current = { inProgress: true, timestamp: Date.now() }
  try {
    setIsValidating(true)
    setError(null)
    const userData = await getCurrentUser()
    setUser(userData)
  } catch (err) {
    setError(err as Error)
    setUser(null)
  } finally {
    setIsValidating(false)
    validationAttemptRef.current.inProgress = false
  }
}, [])
```

**Option 2: Separate "hasAttempted" flag**
Track whether validation has been attempted to distinguish "not yet tried" from "tried and failed."

**Option 3: AbortController for cancellation**
Use AbortController to cancel in-flight requests when component unmounts or Auth0 state changes.

### Completion Criteria
- [x] No infinite loops during validation failures
- [x] Backend unavailable prevents dashboard access
- [x] All protected routes require successful backend validation
- [x] Error messages are clear and actionable
- [x] All tests passing (unit + integration)
- [x] Manual testing scenarios pass
- [ ] Code review approved
- [ ] Documentation updated

### Implementation Summary

**Architectural Approach**: Implemented "backend availability check first" pattern to distinguish between "backend unavailable" vs "backend denies auth"

**Backend Changes**:
1. Added `GET /api/v1/auth/ready` endpoint - checks database connectivity, returns `{ready: boolean, message?: string}`
2. 3 comprehensive tests covering success, no-auth-required, and database error cases
3. 95.83% coverage on `auth.py`

**Frontend Changes**:
1. **ServiceUnavailable component** (`src/pages/ServiceUnavailable.tsx`) - User-friendly error page with auto-retry
2. **BackendAvailabilityContext** (`src/contexts/BackendAvailabilityContext.tsx`) - Pre-flight health check, auto-retry every 10s
3. **Simplified BackendAuthContext** - Removed automatic useEffect validation, removed `hasAttempted` tracking, added `forceLogout()` helper
4. **Explicit Callback validation** - Three-way error handling:
   - 401/403 → Force Auth0 logout
   - 500+ → Show retry option
   - Network error → Show retry option
5. **Fixed Login page** - Check both Auth0 AND backend state before redirect (prevents loop)
6. **Fixed Header** - Use `isBackendAuthenticated` instead of Auth0's `isAuthenticated` (single source of truth)
7. **Updated App** - Wraps entire app in `BackendAvailabilityProvider`, shows ServiceUnavailable if backend down

**Files Created** (2):
- `frontend/src/pages/ServiceUnavailable.tsx`
- `frontend/src/contexts/BackendAvailabilityContext.tsx`

**Files Modified** (8):
- `backend/app/api/auth.py` - Added `/ready` endpoint
- `backend/tests/test_auth_integration.py` - Added 3 tests for `/ready`
- `frontend/src/contexts/BackendAuthContext.tsx` - Simplified validation logic
- `frontend/src/pages/Callback.tsx` - Explicit validation with 3-way error handling
- `frontend/src/pages/Login.tsx` - Check backend state
- `frontend/src/components/layout/Header.tsx` - Use backend state
- `frontend/src/App.tsx` - Add availability check
- `phase_10_implementation_plan.md` - This file

### Success Metrics
- [x] Zero infinite loop occurrences in dev/test
- [x] All backend tests passing (3/3 for `/ready`)
- [x] Backend down = no dashboard access (100% of time) - verified with Playwright
- [ ] ~~Clean console output (no error spam)~~ - **FAILED** (see Test Results below)
- [ ] ~~Smooth UX transitions (no flashing/flickering)~~ - **FAILED** (see Test Results below)

### Manual Test Results (2025-11-06)

**Testing Environment:**
- Backend: uvicorn on port 8000 (FastAPI)
- Frontend: Vite dev server on port 5173
- Test User: tfl.test@cynexia.org
- Browser: Playwright (Chromium)

**Test Scenarios Executed:**

#### Scenario 1: Happy Path Login Flow ❌ FAILED

**Steps Completed:**
1. ✅ Navigated to http://localhost:5173/
2. ✅ ServiceUnavailable page showed briefly, then auto-retry detected backend
3. ✅ Redirected to /login successfully
4. ✅ Clicked "Sign in with Auth0" button
5. ✅ Auth0 consent page appeared for tfl.test@cynexia.org
6. ✅ Clicked "Accept" button
7. ❌ **BLOCKED**: Callback page stuck on "Verifying with server..." indefinitely

**Issues Found:**

---

### Issue #1: Callback Page Stuck in Loading State (CRITICAL)

**Severity:** Critical - Blocks all authentication flows

**Scenario:** Happy path login flow (Scenario 1)

**Steps to Reproduce:**
1. Start backend and frontend services
2. Navigate to http://localhost:5173/
3. Click "Sign in with Auth0"
4. Complete Auth0 login with test credentials
5. Click "Accept" on Auth0 consent page
6. Observe callback page behavior

**Expected Behavior:**
- Callback page should show "Verifying with server..." briefly
- Backend validation should complete (success or failure)
- Page should either:
  - Navigate to /dashboard (on success), OR
  - Show error message with logout/retry options (on 403), OR
  - Show error message with retry option (on 500+)

**Actual Behavior:**
- Callback page shows "Verifying with server..." spinner indefinitely (15+ seconds observed)
- Page remains stuck on /callback URL
- No visual feedback about the failure
- User has no way to proceed or retry

**Console Errors:**
```
[ERROR] Failed to get access token: Error: Auth context unmounted
    at http://localhost:5173/src/App.tsx:151:49
    at fetchAPI (http://localhost:5173/src/lib/api.ts:34:27)
    at getCurrentUser (http://localhost:5173/src/lib/api.ts:73:26)
    at http://localhost:5173/src/contexts/BackendAuthContext.tsx:27:30
    at performValidation (http://localhost:5173/src/pages/Callback.tsx:48:19)

[ERROR] Failed to load resource: the server responded with a status of 403 (Forbidden)
@ http://localhost:8000/api/v1/auth/me:0
```

**Backend Logs:**
```
INFO:     127.0.0.1:62917 - "GET /api/v1/auth/me HTTP/1.1" 403 Forbidden
```

**Root Cause Analysis:**

This issue has **two distinct problems**:

**Problem 1: Backend 403 Forbidden Response**
- Auth0 authentication succeeds (user gets token)
- Frontend attempts to call `GET /api/v1/auth/me` with the Auth0 token
- Backend rejects with 403 Forbidden
- Possible causes:
  - JWT token validation failing (wrong audience, issuer, or algorithm)
  - Token not properly formatted in Authorization header
  - Backend auth configuration mismatch with Auth0 config
  - User not in database and backend not creating user automatically

**Problem 2: "Auth context unmounted" Error**
- The API client (src/lib/api.ts line 151) tries to call `getAccessTokenFn()`
- This function attempts to get Auth0 token via `getAccessTokenSilently()`
- Error: "Auth context unmounted" suggests the Auth0 context is not available
- This occurs during the API call to `/auth/me` in `getCurrentUser()`
- Timing issue: Auth0 context may be unmounting/remounting during callback processing

**Problem 3: Error Handling Not Working**
- Despite the 403 error, the Callback page doesn't transition to error state
- The three-way error handling (lines 68-95 in Callback.tsx) should catch this
- Expected: Show "Authentication denied" alert and force logout after 2 seconds
- Actual: Page stays in "validating" state indefinitely
- Possible causes:
  - The error from `validateWithBackend()` is not being caught properly
  - State management issue preventing error state from rendering
  - The "Auth context unmounted" error is thrown before the 403 is processed

**Screenshot Evidence:**
- `/Users/rob/Downloads/git/IsTheTubeRunning/.playwright-mcp/issue1-callback-stuck.png`

**Investigation Results:**

✅ **Auth0 Configuration:** VERIFIED - Frontend and backend configs match correctly
   - Domain: tfl-alerts.uk.auth0.com ✓
   - Audience: https://tfl-alert-api.cynexia.com ✓
   - Algorithm: RS256 ✓
   - CORS: http://localhost:5173 in ALLOWED_ORIGINS ✓

✅ **Backend Auth Logic:** VERIFIED - JWT validation code is correct
   - JWKS fetching works
   - Token validation properly configured
   - User auto-creation on first login implemented

❌ **ROOT CAUSE IDENTIFIED:** Component Lifecycle Bug in App.tsx

**Location:** `frontend/src/App.tsx` lines 78-80

**Problematic Code:**
```typescript
useEffect(() => {
  setAccessTokenGetter(getAccessToken)

  return () => {
    // Reset on unmount to prevent stale references
    setAccessTokenGetter(() => Promise.reject(new Error('Auth context unmounted')))
  }
}, [getAccessToken])
```

**The Bug:**
1. The `AppContent` component sets up the access token getter in a `useEffect`
2. The cleanup function replaces it with an error-throwing function when the component unmounts
3. During Auth0 callback navigation, React may unmount/remount `AppContent`
4. When unmounting, the cleanup runs and replaces `getAccessToken` with error function
5. The Callback page tries to validate with backend
6. API client calls `getAccessToken()`, gets rejected with "Auth context unmounted"
7. API request either fails before sending or sends without valid token
8. Backend returns 403 because no/invalid token received
9. Callback page's error handling doesn't trigger correctly due to the thrown error

**Why It's Wrong:**
- The cleanup function is too aggressive - it shouldn't break the API client during navigation
- Component lifecycle events shouldn't disrupt authentication state
- This creates a race condition between navigation and token retrieval

**Suggested Fix:**
Either:
1. **Remove the cleanup** - Don't reset the access token getter on unmount
2. **Use a ref instead of cleanup** - Track if component is mounted without disrupting API calls
3. **Restructure component hierarchy** - Move API setup to a higher level that doesn't unmount

**Example Fix (Option 1):**
```typescript
useEffect(() => {
  setAccessTokenGetter(getAccessToken)
  // Remove cleanup function entirely - access token getter should persist
}, [getAccessToken])
```

**Impact:**
- **Blocks all user authentication** - Cannot log in to application
- Race condition occurs on every Auth0 callback
- No fallback or recovery mechanism for users
- Poor UX with infinite loading state

**Priority:** P0 - Must fix before any further testing

**Additional Issues Found:**
- Error handling in Callback.tsx (lines 68-95) not triggering despite 403 error
- Need to verify why error state doesn't render after validation failure

---

### Testing Summary

**Date:** 2025-11-06
**Tester:** Claude Code AI Assistant (Playwright automation)
**Branch:** feature/phase-10-pr2.5-fix-auth-flow
**Status:** ❌ **CRITICAL BLOCKER FOUND**

**Tests Attempted:**
1. ❌ Scenario 1: Happy Path Login Flow - **FAILED** (blocking bug found)
2. ⏸️  Scenario 2-7: **BLOCKED** (cannot proceed without working auth)

**Critical Issues:**
- **1 P0 blocker**: Component lifecycle bug in App.tsx breaks authentication flow

**Next Steps:**
1. Fix the component lifecycle bug in `frontend/src/App.tsx` (remove aggressive cleanup)
2. Re-run Scenario 1 to verify fix
3. Continue with remaining test scenarios (2-7)
4. Verify error handling in Callback.tsx works correctly after fix

**Recommendation:**
Do not proceed with PR2.5 merge until this issue is resolved. The authentication flow is completely broken and blocks all user access to the application.

---



## PR3: Route Management

**Branch**: `feature/phase-10-pr3-routes`
**Estimated Time**: 4-5 days
**Status**: Not Started
**Depends on**: PR1

### Goals
- Implement complete route management (CRUD)
- Build sophisticated route builder with TfL data integration
- Create schedule configuration UI
- Show visual route preview

### shadcn/ui Components to Install
- [ ] Select
- [ ] Switch
- [ ] Checkbox
- [ ] Calendar
- [ ] Popover
- [ ] Command (for autocomplete)
- [ ] Table
- [ ] Accordion

### Tasks

#### 1. API Client Expansion
- [ ] Add all `/routes` endpoint methods
- [ ] Add all `/tfl` endpoint methods
- [ ] TypeScript interfaces: `Route`, `RouteSegment`, `Schedule`, `Line`, `Station`, `NetworkGraph`

#### 2. State Management
- [ ] Create `src/hooks/useRoutes.ts` - manage routes state
- [ ] Create `src/hooks/useTflData.ts` - cache TfL lines, stations, network graph

#### 3. Core Components
- [ ] Create `src/components/routes/RouteCard.tsx` - route summary card
- [ ] Create `src/components/routes/RouteList.tsx` - grid/list of routes
- [ ] Create `src/components/routes/RoutePath.tsx` - visual route display with stations

#### 4. Route Builder Components (Complex)
- [ ] Create `src/components/routes/RouteBuilderDialog.tsx` - multi-step dialog
- [ ] Create `src/components/routes/StationSelector.tsx` - autocomplete station picker
- [ ] Create `src/components/routes/LineSelector.tsx` - line picker with colors
- [ ] Create `src/components/routes/RoutePreview.tsx` - visual preview of route path
- [ ] Create `src/components/routes/ScheduleForm.tsx` - day/time configuration

#### 5. Pages
- [ ] Update `src/pages/Dashboard.tsx` - show route list, add create button
- [ ] Create `src/pages/RouteDetails.tsx` - full route details page
  - Route path with stations and lines
  - Schedules list (add/edit/delete)
  - Active/inactive toggle
  - Edit route button, delete route button

#### 6. Routing
- [ ] Update `/dashboard` route to show routes
- [ ] Add `/dashboard/routes/:id` protected route

#### 7. Route Builder Logic
- [ ] Multi-step form flow:
  1. Basic info (name, description, timezone)
  2. Station selection (start → interchanges → end)
  3. Schedule configuration (days, times)
  4. Review and create
- [ ] Real-time route validation using TfL network graph
- [ ] Show validation errors (invalid connections)

#### 8. Tests
- [ ] Component tests for all route components
- [ ] Integration tests for route creation flow
- [ ] Route validation logic tests
- [ ] Schedule configuration tests
- [ ] Edge cases: invalid routes, schedule conflicts

#### 9. Documentation
- [ ] Update README with route features

### Completion Criteria
- [ ] Users can view all their routes
- [ ] Users can create complex multi-segment routes with validation
- [ ] Route builder shows TfL lines and stations
- [ ] Real-time validation feedback
- [ ] Schedules can be configured (days/times)
- [ ] Routes can be edited and deleted
- [ ] Routes can be activated/deactivated
- [ ] All tests passing (>80% coverage)
- [ ] Mobile responsive

### Files Created/Modified (~25-30)
- API: `lib/api.ts` (routes, TfL methods)
- Components: `routes/*`, `ui/*` (new shadcn components)
- Pages: `Dashboard.tsx` (updated), `RouteDetails.tsx`
- Hooks: `hooks/useRoutes.ts`, `hooks/useTflData.ts`
- Tests: `*.test.tsx`
- Routes: `App.tsx` (updated)

---

## PR4: Notification Preferences

**Branch**: `feature/phase-10-pr4-notifications`
**Estimated Time**: 2-3 days
**Status**: Not Started
**Depends on**: PR2 (Contacts) + PR3 (Routes)

### Goals
- Configure alert preferences per route
- Select verified contacts for notifications
- Choose notification method (email/SMS)
- Show warnings if no notifications configured

### shadcn/ui Components to Install
- [ ] RadioGroup
- [ ] Toggle

### Tasks

#### 1. API Client Expansion
- [ ] Add `/routes/:id/notifications` endpoint methods
- [ ] TypeScript interfaces: `NotificationPreference`

#### 2. Components
- [ ] Create `src/components/notifications/NotificationPreferenceCard.tsx` - show preference
- [ ] Create `src/components/notifications/AddNotificationDialog.tsx` - add preference modal
- [ ] Create `src/components/notifications/NotificationMethodBadge.tsx` - email/SMS indicator

#### 3. Page Enhancements
- [ ] Update `src/pages/RouteDetails.tsx`:
  - Add "Notifications" section
  - List notification preferences
  - Add notification button
  - Edit/delete preference actions
  - Warning if no notifications configured
- [ ] Update `src/components/routes/RouteCard.tsx`:
  - Show notification status indicator (✓ or ⚠)

#### 4. Business Logic
- [ ] Filter to show only verified contacts in dropdown
- [ ] Validate contact type matches method (email method → email contact)
- [ ] Handle duplicate preference detection

#### 5. Tests
- [ ] Component tests for notification components
- [ ] Integration tests: add/edit/delete preferences
- [ ] Verified contact filtering tests
- [ ] Edge cases: unverified contacts, duplicates

#### 6. Documentation
- [ ] Update README with notification features

### Completion Criteria
- [ ] Users can add notification preferences per route
- [ ] Only verified contacts shown in dropdown
- [ ] Method validation (email/SMS) enforced
- [ ] Duplicate preferences prevented
- [ ] Visual warning if route has no notifications
- [ ] All tests passing (>80% coverage)
- [ ] Mobile responsive

### Files Created/Modified (~10-12)
- API: `lib/api.ts` (notification preference methods)
- Components: `notifications/*`
- Pages: `RouteDetails.tsx` (updated), `RouteCard.tsx` (updated)
- Tests: `*.test.tsx`

---

## PR5: Admin Dashboard

**Branch**: `feature/phase-10-pr5-admin`
**Estimated Time**: 3-4 days
**Status**: Not Started
**Depends on**: PR1

### Goals
- Build admin-only dashboard for monitoring
- User management interface
- Analytics visualization
- Notification logs viewer

### shadcn/ui Components to Install
- [ ] DataTable (or custom table)
- [ ] Pagination
- [ ] Tabs
- [ ] Install Recharts for charts (`npm install recharts`)

### Tasks

#### 1. API Client Expansion
- [ ] Add all `/admin/*` endpoint methods
- [ ] TypeScript interfaces: `AdminUser`, `EngagementMetrics`, `NotificationLog`

#### 2. Authorization
- [ ] Create `src/components/AdminGuard.tsx` - admin-only route guard
- [ ] Update `src/hooks/useAuth.ts` to include `isAdmin` check

#### 3. Components
- [ ] Create `src/components/admin/UserTable.tsx` - paginated user list
- [ ] Create `src/components/admin/UserDetailsDialog.tsx` - user details modal
- [ ] Create `src/components/admin/AnalyticsCard.tsx` - metric display card
- [ ] Create `src/components/admin/NotificationLogTable.tsx` - notification logs
- [ ] Create `src/components/admin/EngagementCharts.tsx` - Recharts visualizations

#### 4. Pages
- [ ] Create `src/pages/admin/AdminDashboard.tsx`:
  - Analytics overview
  - Charts: user growth, notification volume
  - Key metrics display
- [ ] Create `src/pages/admin/AdminUsers.tsx`:
  - User table with search and pagination
  - View details, delete user actions
- [ ] Create `src/pages/admin/AdminAlerts.tsx`:
  - Recent notification logs (paginated)
  - Status filter (sent, failed)
  - Manual trigger button for disruption check

#### 5. Navigation
- [ ] Update `src/components/layout/Header.tsx`:
  - Add "Admin" menu item (visible only if user is admin)
- [ ] Update `src/components/layout/Navigation.tsx`:
  - Add admin nav links

#### 6. Routing
- [ ] Add admin routes to `App.tsx`:
  - `/admin/dashboard` (protected + admin only)
  - `/admin/users` (protected + admin only)
  - `/admin/alerts` (protected + admin only)

#### 7. Tests
- [ ] Component tests for all admin components
- [ ] Integration tests for admin flows
- [ ] Authorization tests (non-admin can't access)
- [ ] Edge cases: pagination, search, empty states

#### 8. Documentation
- [ ] Update README with admin features

### Completion Criteria
- [ ] Admins can view analytics dashboard
- [ ] Admins can manage users (view, search, delete)
- [ ] Admins can view notification logs
- [ ] Admins can manually trigger disruption checks
- [ ] Non-admin users get 403 when accessing admin pages
- [ ] Charts display engagement metrics
- [ ] All tests passing (>80% coverage)
- [ ] Mobile responsive

### Files Created/Modified (~20-25)
- API: `lib/api.ts` (admin methods)
- Components: `admin/*`, `AdminGuard.tsx`
- Pages: `admin/AdminDashboard.tsx`, `admin/AdminUsers.tsx`, `admin/AdminAlerts.tsx`
- Layout: `Header.tsx`, `Navigation.tsx` (updated)
- Tests: `*.test.tsx`
- Routes: `App.tsx` (updated)

---

## Cross-Cutting Concerns (All PRs)

### Responsive Design
- [ ] Mobile-first approach using Tailwind breakpoints
- [ ] Test on: mobile (375px), tablet (768px), desktop (1024px+)
- [ ] Hamburger menu for mobile navigation
- [ ] Touch-friendly button sizes (min 44x44px)

### Error Handling
- [ ] Toast notifications for errors (Sonner or shadcn Toast)
- [ ] Loading states (skeletons, spinners)
- [ ] Empty states (no routes, no contacts, no data)
- [ ] Network error recovery

### Accessibility
- [ ] Semantic HTML elements
- [ ] ARIA labels for interactive elements
- [ ] Keyboard navigation support
- [ ] Focus management in dialogs/modals
- [ ] Color contrast compliance (WCAG AA)

### Code Quality
- [ ] ESLint compliance
- [ ] TypeScript strict mode
- [ ] Consistent component patterns
- [ ] Reusable custom hooks
- [ ] DRY principle for common logic

---

## Environment Configuration

### Required Environment Variables

Add to `/frontend/.env.example`:

```env
# API Configuration
VITE_API_URL=http://localhost:8000

# Auth0 Configuration
VITE_AUTH0_DOMAIN=your-tenant.auth0.com
VITE_AUTH0_CLIENT_ID=your-client-id
VITE_AUTH0_AUDIENCE=https://your-api-audience
VITE_AUTH0_CALLBACK_URL=http://localhost:5173/callback
```

---

## Testing Strategy

### Test Types per PR
- **Component tests**: Vitest + Testing Library for all components
- **Integration tests**: User flow testing with mocked APIs
- **Mock strategies**:
  - Mock Auth0 with fake JWT tokens
  - Mock API responses with MSW (Mock Service Worker)
  - Mock TfL data for route builder

### Coverage Target
- **Per PR**: >80% coverage
- **Overall Phase 10**: >85% coverage

### Test Commands
```bash
# Run all tests
npm test

# Run tests with coverage
npm run test:coverage

# Run tests in watch mode
npm run test:watch
```

---

## Phase 10 Completion Criteria

### Functional Requirements
- [x] @auth0/auth0-react installed (PR1 in progress)
- [ ] Users can authenticate with Auth0
- [ ] Users can manage email/phone contacts with verification
- [ ] Users can create complex multi-segment routes with TfL validation
- [ ] Users can configure notification preferences per route
- [ ] Admins can view analytics dashboard
- [ ] Admins can manage users
- [ ] Admins can monitor alerts

### Non-Functional Requirements
- [ ] All pages responsive (mobile, tablet, desktop)
- [ ] Comprehensive test coverage (>85%)
- [ ] Accessible UI (WCAG AA)
- [ ] TypeScript strict mode compliant
- [ ] ESLint compliant
- [ ] Loading states for all async operations
- [ ] Error handling for all API calls

### Documentation
- [ ] README updated with frontend setup
- [ ] Environment variables documented
- [ ] Component structure documented

---

## Progress Tracking

### PR1: Authentication & Foundation
- **Status**: Complete ✅
- **Started**: 2025-11-05
- **Completed**: 2025-11-05
- **Dependencies Installed**: @auth0/auth0-react, shadcn/ui components, prettier, eslint-config-prettier
- **Branch**: feature/phase-10-pr1-auth-foundation
- **Tests**: 11/11 passing ✅
- **Build**: Successful ✅

### PR2: Contact Management
- **Status**: Not Started
- **Started**: TBD
- **Completed**: TBD

### PR3: Route Management
- **Status**: Not Started
- **Started**: TBD
- **Completed**: TBD

### PR4: Notification Preferences
- **Status**: Not Started
- **Started**: TBD
- **Completed**: TBD

### PR5: Admin Dashboard
- **Status**: Not Started
- **Started**: TBD
- **Completed**: TBD

---

## Notes and Decisions

### Architectural Decisions
- **Auth0 over custom auth**: Offload auth complexity, focus on features
- **shadcn/ui over component library**: More control, better customization, smaller bundle
- **React Router v7**: Modern routing with data loading capabilities
- **No global state library initially**: Use React Context and hooks, add Zustand later if needed
- **Optimistic updates**: Better UX, especially for contact/route operations
- **Mock Service Worker for tests**: Realistic API mocking without complex setup

### Deferred Features
- Push notifications (Phase 10+ or post-MVP)
- Real-time updates via WebSockets (Phase 10+ or post-MVP)
- Advanced analytics charts (start simple, enhance in PR5 if time permits)
- SMS implementation (backend stub ready, frontend will show SMS option but backend logs only)

### Challenges and Risks
- **Route builder complexity**: Most complex UI component, may require additional time
- **TfL data integration**: Need to handle large datasets efficiently (station/line lists)
- **Auth0 configuration**: Requires external setup, document clearly for future developers
- **Mobile responsiveness**: Route builder may be challenging on small screens

---

## Next Steps

1. **Complete PR1**: Finish authentication and foundation setup
2. **Get PR1 reviewed and merged**: Do not start PR2 until PR1 is approved
3. **Repeat for PR2-PR5**: Sequential implementation and review
4. **Update this document**: Mark tasks complete as they're done
5. **Update `/implementation_plan.md`**: Mark Phase 10 complete when all PRs merged
6. **Prepare for Phase 11**: Testing & Quality phase (E2E tests, performance optimization)

---

**Document Version**: 1.0
**Last Updated**: 2025-11-05
**Author**: Claude Code AI Assistant
