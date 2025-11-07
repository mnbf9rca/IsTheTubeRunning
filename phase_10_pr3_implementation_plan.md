# Phase 10 - PR3: Route Management - Split Implementation Plan

**Parent Phase**: Phase 10 - Frontend Development
**Original PR**: PR3 (Route Management)
**Decision**: Split into 2 focused PRs for manageability
**Created**: 2025-11-07

---

## Split Rationale

The original PR3 scope (4-5 days, 25-30 files) was too large. Split into:
- **PR3a**: Routes Foundation (basic CRUD, metadata only)
- **PR3b**: Route Builder & Schedules (segments, schedules, TfL integration)

This split allows:
- Smaller, focused pull requests
- Easier code review
- Faster iteration
- Clear separation of concerns

---

## PR3a: Routes Foundation ✅ COMPLETE

**Branch**: `feature/phase-10-pr3a-routes-foundation`
**Estimated Time**: 2-3 days
**Actual Time**: 1 day
**Status**: Complete ✅
**Started**: 2025-11-07
**Completed**: 2025-11-07
**Depends on**: PR2.5 (Backend Auth Architecture)

### Goals
- Implement basic route CRUD operations (create, read, update, delete)
- Build routes listing page with route cards
- Allow users to create/edit route metadata (name, description, active, timezone)
- Establish patterns for PR3b

### Tasks Completed

#### 1. shadcn/ui Components Installed
- [x] Select - Already installed
- [x] Switch - Already installed
- [x] Tabs - Already installed
- [x] Form - Not needed (using simple forms)

#### 2. API Client Extension (`frontend/src/lib/api.ts`)
- [x] TypeScript interfaces added:
  - `RouteListItemResponse` - Summary for lists
  - `RouteResponse` - Full route with segments/schedules
  - `SegmentResponse` - Segment information
  - `ScheduleResponse` - Schedule information
  - `CreateRouteRequest` - Route creation data
  - `UpdateRouteRequest` - Route update data (partial)
- [x] API methods implemented:
  - `getRoutes()` → GET /routes
  - `getRoute(routeId)` → GET /routes/{id}
  - `createRoute(data)` → POST /routes
  - `updateRoute(routeId, data)` → PATCH /routes/{id}
  - `deleteRoute(routeId)` → DELETE /routes/{id}

#### 3. Custom Hook Created
- [x] `src/hooks/useRoutes.ts` - Route state management
  - State: routes, loading, error
  - Methods: refresh, createRoute, updateRoute, deleteRoute, getRoute
  - Auto-fetch on mount
  - Follows useContacts pattern

#### 4. Components Created (`frontend/src/components/routes/`)
- [x] **RouteCard.tsx** - Display route summary card
  - Shows name, description, active badge
  - Displays segment count, schedule count
  - Shows timezone
  - Edit and delete buttons
  - Optional onClick for navigation
  - isDeleting state support
- [x] **RouteList.tsx** - Grid of route cards
  - Loading state (3 skeleton cards)
  - Empty state with helpful message
  - Grid layout (responsive: 1/2/3 columns)
  - Passes through onClick, onEdit, onDelete
- [x] **RouteFormDialog.tsx** - Create/edit route metadata
  - Name input (required, max 255 chars)
  - Description input (optional)
  - Timezone selector (8 common timezones)
  - Active switch with description
  - Dual mode: create vs edit
  - Client-side validation
  - Error handling with Alert component

#### 5. Pages Created/Updated
- [x] **Routes.tsx** - Main routes management page
  - Header with "Create Route" button
  - Route list with RouteCard components
  - Create dialog integration
  - Edit dialog integration
  - Delete confirmation dialog
  - Loading and error states
  - Toast notifications for success/errors
- [x] **Dashboard.tsx** - Updated to show real route count
  - Integrated useRoutes hook
  - Shows actual route count (not "0")
  - Shows active route count
  - Routes card is clickable → navigates to /routes
  - Loading state support

#### 6. Routing Updated
- [x] Added `/routes` protected route to `App.tsx`
- [x] Fixed Navigation.tsx - Routes link now points to `/routes` (was `/dashboard`)

#### 7. Tests Written (All Passing ✅)
- [x] `useRoutes.test.ts` - Hook tests (11 tests)
  - Initialization and fetch
  - Create, update, delete operations
  - Error handling with waitFor()
  - Refresh functionality
- [x] `RouteCard.test.tsx` - Component tests (8 tests)
  - Renders route information correctly
  - Active/inactive badge display
  - Button interactions (edit, delete, click)
  - Disabled state when deleting
- [x] `RouteList.test.tsx` - Component tests (5 tests)
  - Loading state with skeletons
  - Empty state display
  - List rendering
  - Pass-through of handlers
- [x] `Routes.test.tsx` - Page integration tests (10 tests)
  - Page header rendering
  - Create button and dialog
  - Loading and error states
  - Auth error handling
  - Delete confirmation flow

#### 8. Code Quality
- [x] TypeScript strict mode compliant
- [x] ESLint zero errors, zero warnings
- [x] Prettier formatted
- [x] Production build successful

### Test Results
- **Total**: 137/137 tests passing (100%)
- **Coverage**: Exceeds 80% target
- **Quality**: All checks passed

### Files Created (12 files)
- `src/hooks/useRoutes.ts`
- `src/hooks/useRoutes.test.ts`
- `src/components/routes/RouteCard.tsx`
- `src/components/routes/RouteCard.test.tsx`
- `src/components/routes/RouteList.tsx`
- `src/components/routes/RouteList.test.tsx`
- `src/components/routes/RouteFormDialog.tsx`
- `src/pages/Routes.tsx`
- `src/pages/Routes.test.tsx`

### Files Modified (5 files)
- `src/lib/api.ts` - Added route types & methods
- `src/pages/Dashboard.tsx` - Added real route count
- `src/App.tsx` - Added /routes route
- `src/test/setup.ts` - Added ResizeObserver mock
- `src/components/layout/Navigation.tsx` - Fixed Routes href

### Completion Criteria Met
- [x] Users can view all their routes
- [x] Users can create routes (metadata only, no segments yet)
- [x] Users can edit route metadata
- [x] Users can delete routes
- [x] Users can activate/deactivate routes
- [x] Dashboard shows real route count
- [x] Navigation links to routes page
- [x] All tests passing (>80% coverage)
- [x] Mobile responsive
- [x] TypeScript strict mode
- [x] ESLint clean
- [x] Production build successful

### Ready for PR
Branch `feature/phase-10-pr3a-routes-foundation` is ready for review and merge.

---

## PR3b: Route Builder & Schedules

**Branch**: `feature/phase-10-pr3b-route-builder`
**Estimated Time**: 2-3 days
**Status**: Not Started
**Depends on**: PR3a merged to main

### Goals
- Implement segment management with real-time validation
- Build schedule configuration UI
- Integrate TfL data (stations, lines, network graph)
- Create complete route building experience

### shadcn/ui Components to Install
- [ ] Checkbox (for days of week)
- [ ] Command (for autocomplete station picker)
- [ ] Calendar (if needed for date picking)
- [ ] Popover (for combobox)
- [ ] Accordion (for collapsible sections)

### Tasks

#### 1. API Client Expansion (`frontend/src/lib/api.ts`)
Add TypeScript interfaces:
- [ ] `LineResponse` - TfL line data
- [ ] `StationResponse` - TfL station data
- [ ] `NetworkGraph` - Station connections
- [ ] `RouteValidationResponse` - Validation result
- [ ] `SegmentRequest` - Segment creation data
- [ ] `UpsertSegmentsRequest` - Replace all segments
- [ ] `CreateScheduleRequest` - Schedule creation
- [ ] `UpdateScheduleRequest` - Schedule update

Add route methods:
- [ ] `updateRouteSegments(routeId, segments)` → PUT /routes/{id}/segments
- [ ] `deleteRouteSegment(routeId, sequence)` → DELETE /routes/{id}/segments/{seq}
- [ ] `createSchedule(routeId, data)` → POST /routes/{id}/schedules
- [ ] `updateSchedule(routeId, scheduleId, data)` → PATCH /routes/{id}/schedules/{id}
- [ ] `deleteSchedule(routeId, scheduleId)` → DELETE /routes/{id}/schedules/{id}

Add TfL methods:
- [ ] `getTflLines()` → GET /tfl/lines
- [ ] `getTflStations(lineId?)` → GET /tfl/stations
- [ ] `validateRoute(segments)` → POST /tfl/validate-route
- [ ] `getNetworkGraph()` → GET /tfl/network-graph

#### 2. State Management
- [ ] Create `src/hooks/useTfLData.ts` - TfL data caching
  - Fetch and cache lines
  - Fetch and cache stations (all or by line)
  - Fetch network graph
  - Loading states for each resource
  - Methods: getLines, getStations, validateRoute

#### 3. Route Builder Components (`frontend/src/components/routes/`)
- [ ] **SegmentForm.tsx** - Add/edit single segment
  - Station selector (searchable)
  - Line selector
  - Sequence indicator
- [ ] **SegmentList.tsx** - Ordered list of segments
  - Visual route path display
  - Reorder segments (if needed)
  - Delete segment with resequencing
  - Minimum 2 segments validation
- [ ] **StationCombobox.tsx** - Searchable station picker
  - Uses Command component
  - Filters stations by search
  - Shows station name
- [ ] **LineSelect.tsx** - Line picker with colors
  - Dropdown of TfL lines
  - Shows line name and color indicator
- [ ] **RouteValidationAlert.tsx** - Show validation errors/warnings
  - Displays validation messages
  - Highlights invalid segment
  - Success state

#### 4. Schedule Components (`frontend/src/components/routes/`)
- [ ] **ScheduleForm.tsx** - Day picker + time inputs
  - Checkboxes for days of week (MON-SUN)
  - Time inputs (start, end)
  - Validation: end_time > start_time
- [ ] **ScheduleCard.tsx** - Display schedule
  - Shows days as badges
  - Shows time range
  - Edit and delete buttons
- [ ] **ScheduleList.tsx** - List of schedules
  - Empty state
  - Add schedule button

#### 5. Pages
- [ ] Create `src/pages/RouteDetails.tsx` - Full route details
  - Tabs: Overview, Segments, Schedules
  - **Overview tab**:
    - Route metadata (name, desc, timezone)
    - Active toggle
    - Edit metadata button
  - **Segments tab**:
    - SegmentList component
    - Add Segment button
    - Real-time validation display
    - Save changes button
  - **Schedules tab**:
    - ScheduleList component
    - Add Schedule button
  - Breadcrumb: Routes > {Route Name}
  - Delete route button

#### 6. Routing
- [ ] Update `src/pages/Routes.tsx`:
  - Make route cards clickable → navigate to `/routes/{id}`
- [ ] Add `/routes/:id` protected route to `App.tsx`

#### 7. Real-Time Validation Logic
- [ ] After each segment add/edit/delete:
  - Call `validateRoute()` API
  - Display validation result
  - Disable save if invalid
  - Show which segment has issue

#### 8. Tests (Vitest)
- [ ] `useTfLData.test.ts` - TfL data fetching and caching
- [ ] `SegmentForm.test.tsx` - Segment creation/editing
- [ ] `SegmentList.test.tsx` - Segment list with reordering
- [ ] `ScheduleForm.test.tsx` - Schedule configuration
- [ ] `ScheduleCard.test.tsx` - Schedule display
- [ ] `RouteDetails.test.tsx` - Page integration tests
- [ ] Mock TfL API responses
- [ ] Target: >80% coverage

#### 9. Validation
- [ ] TypeScript strict mode compliant
- [ ] ESLint clean
- [ ] Prettier formatted
- [ ] Build succeeds

### Completion Criteria
- [ ] Users can add/edit/delete segments to routes
- [ ] Real-time validation shows errors immediately
- [ ] Station and line pickers work with TfL data
- [ ] Users can configure schedules (days + times)
- [ ] Users can view/edit/delete schedules
- [ ] Route details page shows all route info
- [ ] All tests passing (>80% coverage)
- [ ] Mobile responsive

### Files to Create/Modify (~18-20)
- API: `lib/api.ts` (TfL + segment/schedule methods)
- Hooks: `hooks/useTfLData.ts` + test
- Components: `routes/SegmentForm.tsx`, `routes/SegmentList.tsx`, `routes/StationCombobox.tsx`, `routes/LineSelect.tsx`, `routes/RouteValidationAlert.tsx`, `routes/ScheduleForm.tsx`, `routes/ScheduleCard.tsx`, `routes/ScheduleList.tsx` + tests
- Pages: `pages/RouteDetails.tsx` + test, `pages/Routes.tsx` (updated)
- Routes: `App.tsx` (add /routes/:id)

---

## Progress Tracking

### PR3a Status: Complete ✅
- Merged to main: [pending]
- All acceptance criteria met
- Ready for production

### PR3b Status: Not Started
- Awaiting PR3a merge
- Implementation to begin after PR3a is in main

---

## Notes

### Design Decisions
- **Simple Forms over Complex Wizards**: Following YAGNI, using straightforward form components instead of multi-step wizards
- **Real-time Validation**: Balancing UX (immediate feedback) with API efficiency
- **Component Reusability**: SegmentForm and ScheduleForm designed for both create and edit modes

### Deferred to PR3b
- Route details view/edit
- Segment management
- Schedule configuration
- TfL data integration
- Visual route preview

### Integration Points
- PR3a provides foundation: useRoutes hook, RouteCard, RouteList, Routes page
- PR3b extends: adds segment/schedule management to existing routes

---

**Document Version**: 1.0
**Last Updated**: 2025-11-07
**Author**: Claude Code AI Assistant
