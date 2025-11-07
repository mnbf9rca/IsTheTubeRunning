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
- [ ] Primary contact can be set. Deferred until needed *YAGNI)
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
**Status**: Complete ✅ Merged ✅
**Priority**: CRITICAL - Blocks PR3, PR4, PR5
**Started**: 2025-11-05
**Completed**: 2025-11-06
**Depends on**: PR2

### Summary
Fixed critical authentication architecture issues to make backend the single source of truth for authentication state. Implemented backend availability check pattern to distinguish between "backend unavailable" and "backend denies auth", resolving infinite loop bugs and improving error handling.

See [Authentication & Authorization ADRs](../../docs/adr/04-authentication.md) for architectural decisions.



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
- **Status**: Complete ✅ Merged ✅
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

### PR2.5: Backend Auth Architecture
- **Status**: Complete ✅ Merged ✅
- **Started**: 2025-11-05
- **Completed**: 2025-11-06
- **Branch**: feature/phase-10-pr2.5-fix-auth-flow
- **Tests**: All passing (backend 10/10, frontend 16/16) ✅
- **Build**: Successful ✅

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
