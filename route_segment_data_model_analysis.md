# Route Segment Data Model Analysis

**Date**: 2025-11-07
**Issue**: Data model mismatch between conceptual route representation and database schema
**Status**: ✅ RESOLVED - Option 1 (Nullable line_id) implemented on 2025-11-07

---

## Problem Statement

Users create routes by selecting stations and lines. The conceptual model is:

**"From Station A, take Line X to Station B"**

However, the current database schema stores segments as `{station_id, line_id}`, which creates confusion about what the `line_id` represents at destination/terminating stations.

---

## Current Database Schema

### Table: `route_segments`

```sql
CREATE TABLE route_segments (
    id UUID PRIMARY KEY,
    route_id UUID NOT NULL REFERENCES routes(id),
    sequence INTEGER NOT NULL,
    station_id UUID NOT NULL REFERENCES stations(id),
    line_id UUID NOT NULL REFERENCES lines(id),

    UNIQUE (route_id, sequence)
);
```

### Current Data Model Interpretation

For a route: **Southgate → Leicester Square**

| Sequence | Station ID | Line ID | Meaning |
|----------|------------|---------|---------|
| 0 | Southgate | Piccadilly | "At Southgate, take Piccadilly" |
| 1 | Leicester Square | ??? | "At Leicester Square, take ???" |

**Problem**: What does `line_id` mean for the destination station?
- There's no line to take - the journey ends here
- We're forced to store a line_id due to NOT NULL constraint
- This line_id is meaningless for validation and confusing for users

---

## How Validation Currently Works

**File**: `backend/app/services/tfl_service.py` (lines 1279-1310)

```python
for i in range(len(segments) - 1):
    current_segment = segments[i]
    next_segment = segments[i + 1]

    # Check if connection exists
    is_connected = await self._check_connection(
        from_station_id=current_segment.station_id,
        to_station_id=next_segment.station_id,
        line_id=current_segment.line_id,  # ← Uses segment[i].line_id
    )
```

**Key observation**:
- Only `current_segment.line_id` is used to validate connection to next station
- `next_segment.line_id` is **never used** in validation (loop ends at `len(segments) - 1`)
- The last segment's `line_id` is purely for display purposes

---

## Conceptual Models Comparison

### Model A: Current Schema (Station + Line per segment)

```
Segment 0: {station: Southgate, line: Piccadilly}
Segment 1: {station: Leicester Square, line: ???}
```

**Issues**:
- Requires meaningless line_id for destination
- Confusing: "Leicester Square on Piccadilly" doesn't describe a journey

### Model B: Station + Outgoing Line (Travel from this station)

```
Segment 0: {station: Southgate, line: Piccadilly}
  → Meaning: "From Southgate, travel on Piccadilly"
Segment 1: {station: Leicester Square, line: NULL}
  → Meaning: "Arrive at Leicester Square (journey ends)"
```

**Advantages**:
- line_id clearly means "outgoing line from this station"
- NULL for terminating stations makes semantic sense
- Matches user mental model

### Model C: Connection-based (From Station + Line + To Station)

```
Connection 0: {from_station: Southgate, line: Piccadilly, to_station: Leicester Square}
```

**Advantages**:
- Most explicit representation
- Directly represents "Station A on Line X to Station B"
- No ambiguity about what line_id means

**Disadvantages**:
- Requires schema migration (although we have no user data to migrate)
- Changes validation logic
- More complex for multi-segment routes

---

## Real-World Examples

### Example 1: Simple Route (Southgate → Leicester Square)

**User Intent**: "From Southgate, take Piccadilly line to Leicester Square"

| Model | Segments |
|-------|----------|
| **Current** | [{Southgate, Piccadilly}, {Leicester Square, Piccadilly}] ← Redundant |
| **Model B** | [{Southgate, Piccadilly}, {Leicester Square, NULL}] ← Clear |
| **Model C** | [{from: Southgate, line: Piccadilly, to: Leicester Square}] ← Explicit |

### Example 2: Route with Interchange (Southgate → Leicester Square → Waterloo)

**User Intent**:
1. "From Southgate, take Piccadilly to Leicester Square"
2. "From Leicester Square, take Northern to Waterloo"

| Model | Segments |
|-------|----------|
| **Current** | [{Southgate, Piccadilly}, {Leicester Square, Northern}, {Waterloo, Northern}] ← Last is redundant |
| **Model B** | [{Southgate, Piccadilly}, {Leicester Square, Northern}, {Waterloo, NULL}] ← Clear |
| **Model C** | [{from: Southgate, line: Piccadilly, to: Leicester Square}, {from: Leicester Square, line: Northern, to: Waterloo}] ← Explicit |

---

## Impact Analysis

### Option 1: Make `line_id` Nullable (Model B)

**Database Changes**:
```sql
ALTER TABLE route_segments
ALTER COLUMN line_id DROP NOT NULL;
```

**Backend Changes**:
- Update model: `line_id: Mapped[uuid.UUID | None]`
- Update schemas: `line_id: UUID | None`
- Update validation: Skip validation if `line_id` is NULL (terminating segment)
- Update display logic: Show "Arrival at X" instead of "X on Y line"

**Frontend Changes**:
- Hide line selector for destination stations
- Set `line_id: null` when adding destination
- Only show line selector when "Continue journey" or "Change line" is clicked

**Pros**:
- Minimal schema change (one column constraint)
- Clear semantics: NULL = journey ends here
- Matches user mental model

**Cons**:
- Nullable field adds complexity
- Need to update all existing routes in migration (although we have no user data to migrate)
- Validation logic needs to handle NULL case

### Option 2: Restructure to Connection Model (Model C)

**Database Changes**:
```sql
-- New schema
CREATE TABLE route_connections (
    id UUID PRIMARY KEY,
    route_id UUID NOT NULL REFERENCES routes(id),
    sequence INTEGER NOT NULL,
    from_station_id UUID NOT NULL REFERENCES stations(id),
    line_id UUID NOT NULL REFERENCES lines(id),
    to_station_id UUID NOT NULL REFERENCES stations(id),

    UNIQUE (route_id, sequence)
);
```

**Backend Changes**:
- Complete model rewrite
- Schema changes
- Validation logic rewrite (simpler - one connection = one validation)
- Display logic changes

**Frontend Changes**:
- Complete UX rewrite
- Add "from station" + "line" + "to station" in one step
- Simpler mental model for users

**Pros**:
- Most explicit and clear
- Validation becomes 1:1 with segments
- No meaningless data

**Cons**:
- Major schema migration (although we have no user data to migrate)
- All existing code needs updating
- More disruptive change

### Option 3: Keep Current Schema, Hide the Issue (Status Quo + UX fixes)

**No Database Changes**

**Backend Changes**:
- None

**Frontend Changes**:
- Auto-fill destination's line_id with arrival line
- Hide line selector for destinations
- Show line selector only for interchanges

**Pros**:
- No migration needed
- Minimal changes

**Cons**:
- Data model remains conceptually incorrect
- Storing meaningless data
- Future developers will be confused

### Option 4: Sentinel/Dummy Line (e.g., "TERMINATES")

**Database Changes**:
```sql
-- Add a special "terminating" line
INSERT INTO lines (id, tfl_id, name, color, last_updated)
VALUES (
    '00000000-0000-0000-0000-000000000000',  -- Well-known UUID
    'TERMINATES',
    'Journey Terminates',
    '#000000',
    NOW()
);
```

**Backend Changes**:
- Add constant: `TERMINATES_LINE_ID = UUID('00000000-0000-0000-0000-000000000000')`
- Update validation: Skip validation if `line_id == TERMINATES_LINE_ID`
- Update display logic: Don't show "TERMINATES" line in UI
- Filter out TERMINATES line from line lists

**Frontend Changes**:
- Set `line_id = TERMINATES_LINE_ID` for destination stations
- Hide line selector for destinations
- Filter TERMINATES line from all line selectors

**Pros**:
- No nullable fields (avoids NULL handling complexity)
- Clear sentinel value: explicitly marks terminating segments
- Easier queries (no NULL checks needed)
- No schema change (just data insertion)

**Cons**:
- Feels like a hack/workaround
- Pollutes lines table with fake data
- Still storing meaningless data (just using sentinel instead of NULL)
- Need to filter out fake line everywhere in UI
- Could confuse developers: "What is TERMINATES line?"
- Need to prevent users from selecting TERMINATES line manually
- Migration still needed to update existing last segments

**Comparison to Option 1 (Nullable)**:
- Both require migration to update existing data
- Nullable is more semantically correct (NULL = "no value")
- Sentinel is operationally simpler (no NULL checks)
- Sentinel adds clutter to domain model

---

## Recommendation

**Option 1: Make `line_id` Nullable** (Model B)

**Rationale**:
1. **Minimal disruption**: Single column constraint change
2. **Clear semantics**: NULL explicitly means "no value" (standard SQL pattern)
3. **Matches user intent**: Line only needed when departing from a station
4. **Proper data modeling**: Don't store meaningless values
5. **Cleaner than sentinel**: No fake data in domain model

**Why not Option 4 (Sentinel line)?**
- While avoiding NULL checks is nice, it pollutes the domain model with fake data
- Every query needs to filter out TERMINATES line
- Semantically, NULL is the correct representation of "no outgoing line"
- The operational complexity of NULL handling is minimal with modern ORMs

**Implementation Steps**:
1. Write migration to:
   - Make `line_id` nullable
   - For existing routes, set last segment's `line_id = NULL`
2. Update backend models and schemas
3. Update validation logic to skip NULL line_id segments
4. Update frontend to send `line_id: null` for destinations
5. Update display components to handle NULL line_id
6. Add tests for NULL line_id handling

---

## Questions for Discussion

1. **Do we agree that the last segment's `line_id` is meaningless?**
   - If no, what does it represent?

2. **Is Model B (nullable line_id) the right approach?**
   - Or should we consider Model C (connection-based)?

3. **Are there other use cases we're missing?**
   - Round-trip routes?
   - Routes where you want to specify which line you arrived on for some reason?

4. **Impact on existing data**:
   - How many routes exist in production?
   - Can we safely set last segment's line_id to NULL in migration?  (we have no user data to migrate)

---

## Next Steps

Based on decision:

### If Option 1 (Nullable line_id):
1. [ ] Create Alembic migration
2. [ ] Update SQLAlchemy model
3. [ ] Update Pydantic schemas
4. [ ] Update validation logic
5. [ ] Update frontend SegmentBuilder
6. [ ] Update tests
7. [ ] Test migration with sample data (although we have no user data to migrate)

### If Option 2 (Connection model):
1. [ ] Design new schema in detail
2. [ ] Write migration strategy
3. [ ] Plan phased rollout
4. [ ] Update all affected code

### If Option 3 (Keep as-is):
1. [ ] Document the quirk
2. [ ] Accept technical debt
3. [ ] Complete UX hiding (already done)

### If Option 4 (Sentinel line):
1. [ ] Create TERMINATES line in database
2. [ ] Add constant to codebase
3. [ ] Update validation logic to skip TERMINATES
4. [ ] Add filters to exclude TERMINATES from UI
5. [ ] Update frontend to use TERMINATES_LINE_ID
6. [ ] Write migration to update existing routes
7. [ ] Add tests for TERMINATES handling

---

## Implementation Summary (2025-11-07)

**Decision**: Implemented Option 1 (Nullable line_id)

### Changes Made

#### Backend
1. ✅ **Migration** (`958e140c30a0_make_route_segment_line_id_nullable.py`):
   - Made `route_segments.line_id` nullable using `ALTER COLUMN`
   - No data migration needed (development project with no production data)

2. ✅ **Models** (`backend/app/models/route.py`):
   - Updated `RouteSegment.line_id` to `Mapped[uuid.UUID | None]`

3. ✅ **Schemas**:
   - `backend/app/schemas/routes.py`: `SegmentRequest.line_id` and `SegmentResponse.line_id` → `UUID | None`
   - `backend/app/schemas/tfl.py`: `RouteSegmentRequest.line_id` → `UUID | None`

4. ✅ **Validation** (`backend/app/services/tfl_service.py:1283-1294`):
   - Added NULL check for intermediate segments (only destination can have NULL line_id)
   - Validation loop skips last segment (as it always did)
   - Clear error message: "Segment X must have a line_id. Only the final destination segment can have NULL line_id."

5. ✅ **Tests** (`backend/tests/test_tfl_service.py`):
   - `test_validate_route_with_null_destination_line_id`: Validates NULL is accepted for destination
   - `test_validate_route_with_null_intermediate_line_id`: Validates NULL is rejected for intermediate segments
   - All 81 TfL service tests passing

#### Frontend
1. ✅ **Type Definitions** (`frontend/src/lib/api.ts`):
   - `SegmentRequest.line_id` and `SegmentResponse.line_id` → `string | null`

2. ✅ **SegmentBuilder** (`frontend/src/components/routes/SegmentBuilder.tsx`):
   - `handleSave()`: Automatically sets last segment's `line_id` to `null` before validation and saving
   - Auto-fill logic updated to handle NULL line_id from previous segments
   - User experience unchanged (transparent handling)

3. ✅ **Display Components**:
   - `SegmentDisplay.tsx`: Shows "Destination" label for segments with NULL line_id
   - `SegmentList.tsx`: Passes NULL to SegmentCard when line_id is NULL
   - `SegmentCard.tsx`: Updated props to accept optional `lineName` and `lineColor`, displays "Destination" when both are NULL

4. ✅ **Tests**:
   - All 212 frontend tests passing
   - No test updates required (existing tests continue to work with auto-fill workaround)

### Benefits Achieved
- ✅ **Semantic Correctness**: NULL clearly means "no outgoing line" (journey terminates here)
- ✅ **No Redundant Data**: Last segment no longer stores meaningless line_id
- ✅ **Clear Validation**: Explicit NULL check prevents misuse
- ✅ **Backward Compatible**: Frontend auto-fills for smooth UX transition
- ✅ **Well Tested**: 81 backend + 212 frontend tests passing

### User Experience
- **Route Creation**: Users continue to build routes as before
- **Display**: Destination stations now show "Destination" label instead of redundant line information
- **Validation**: Backend rejects routes with NULL line_id on non-terminal segments with clear error messages

### Technical Debt Eliminated
- ✅ Data model now matches domain model
- ✅ Validation logic conceptually complete
- ✅ No confusion for future developers
- ✅ DRY principle restored (line not specified twice)

---

## UX Issues Discovered During Testing (2025-11-07)

**Testing Session**: Playwright MCP testing of route builder UI
**Route Tested**: Southgate → Leicester Square (Piccadilly line)

### Defects Identified

#### Defect #1: Line Auto-Fills for Starting Station (NOT A DEFECT - ANALYSIS ERROR)
**Issue**: When adding the very first station to a route, the line dropdown automatically populates with a line value.

**Analysis**: This is actually CORRECT behavior - Southgate Underground Station only has one line (Piccadilly). Auto-filling when only one line exists is good UX.

**Corrected Understanding**: Auto-fill is appropriate when:
- Station only has one line (like Southgate → Piccadilly)
- Continuing from previous segment (auto-fill current travel line)

**Impact**: No defect - working as intended.

#### Defect #2: Line Auto-Fills for Terminal Station
**Issue**: When adding the destination/terminal station, the line dropdown automatically populates with the current travel line.

**Expected Behavior**: Terminal station should have `line_id: null` (no outgoing line).

**Current Behavior**: Leicester Square (destination) shows "Piccadilly" auto-filled.

**Impact**:
- Data model violation (terminal segment should have NULL line_id per backend implementation)
- Frontend workaround sets it to NULL on save, but this is hidden from user
- Confusing UX - why does destination need a line?

#### Defect #3: No Way to Unselect Line
**Issue**: Once a line is selected (or auto-filled), there's no way to set it back to NULL/empty.

**Current Behavior**: Line dropdown only shows "Northern" and "Piccadilly" options (lines available at Leicester Square).

**Expected Behavior**: Should have option like "None" or "Not applicable" to unselect.

**Impact**:
- User cannot manually correct auto-filled values
- Cannot express "arrival without continuing"
- Forces user to accept auto-filled value even if incorrect

#### Defect #4: Misleading Label
**Issue**: The line field label says "Line (optional - auto-fills from current line)" for all segments.

**Current Behavior**: Same label for starting station, intermediate stations, and terminal station.

**Expected Behavior**:
- Starting station: "Line *" (required, no auto-fill)
- Intermediate stations: "Line (optional - continue on <current line> or change lines)"
- Terminal station: Should not show line selector at all, or show "Destination" message

**Impact**: Confusing instructions - doesn't communicate when line is truly optional vs. required.

#### Defect #5: "Save Segments" Button Unclear
**Issue**: Clicking "Save Segments" provides no clear feedback about what happened.

**Current Behavior**: Button remains enabled, no visual change, unclear if save succeeded.

**Expected Behavior**:
- Button should disable after successful save, OR
- Show success message/toast, OR
- Hide the segment builder UI and show read-only view

**Impact**: User doesn't know if their action succeeded or if they need to do something else.

---

## Proposed UX Improvements

### Option A: Simplified Sequential Flow (Recommended for Hobby Project - KISS)

**Remove line selection entirely for terminal stations.**

**Flow**:
1. Add starting station → manually select line
2. Add next station →
   - Auto-fill line from previous segment
   - Show message: "Continuing on <Line Name> line" or "Change line:"
   - If user wants to change: click dropdown, select different line
   - Option to "clear" and set to null (shown as "Arriving at destination")
3. Terminal station detection:
   - If user doesn't add another segment after clicking "Add Segment", treat current as terminal
   - Automatically set `line_id: null` for terminal segment
   - Show "Destination" badge instead of line info

**Changes Required**:
- Add "None (Destination)" option to line dropdown
- Update SegmentBuilder logic to detect terminal segment
- Show different UI for terminal vs. intermediate segments
- Auto-save on segment add (remove separate "Save Segments" button confusion)

**Benefits**:
- Simpler UX - less clicking
- Clear visual distinction between terminal and intermediate stations
- Matches user mental model: "traveling on a line" vs. "arriving at destination"

### Option B: Button-Based Line Selection

**Replace dropdown with buttons/chips for better UX.**

**Visual Design**:
```
Station: [Southgate Underground Station ▼]

Traveling on line:
[ Piccadilly ] ← Button/chip (colored with line color)
[+ Add another station] [✓ This is my destination]
```

**If user clicks "+ Add another station"**:
- Shows next station selector
- Auto-fills line or allows change

**If user clicks "This is my destination"**:
- Sets `line_id: null`
- Shows "Destination" badge
- Hides line selector

**Changes Required**:
- Complete redesign of SegmentBuilder component
- Button-based UI instead of dropdown
- More visual/intuitive

**Benefits**:
- Much clearer user intent
- Explicit "destination" marker
- Better mobile experience (large tap targets)

**Drawbacks**:
- Larger implementation effort
- May be over-engineered for hobby project

### Option C: Keep Current Approach, Fix Defects Only (Minimal Change)

**Just fix the specific defects without major UX redesign.**

**Changes**:
1. Add "None (Destination)" option to line dropdown
2. Don't auto-fill line for first station
3. Update label based on segment position:
   - First: "Line *"
   - Middle: "Line (optional - change if switching lines)"
   - Would-be-last: "Line (optional - leave empty if destination)"
4. Change "Save Segments" to show toast notification on success

**Benefits**:
- Minimal code changes
- Addresses all defects

**Drawbacks**:
- Still somewhat confusing UX
- "Line (optional - leave empty if destination)" is wordy
- Doesn't fundamentally improve mental model

---

## Recommendation for Implementation

**Selected Approach**: **Option B - Button-Based Interface** (User Choice)

**Key Requirements from User**:
1. **Journey Model**: STATION→LINE→STATION (line is the edge between two vertices)
2. **Minimum 2 Stations**: Need at least 2 stations to form a valid journey segment
3. **Manual Save**: Keep separate save button with confirmation tick
4. **Post-Save Behavior**: Move user to next section (Active Times) or show validation errors in context
5. **Terminal Detection**: User explicitly marks with "✓ This is my destination" button

**Implementation Complexity**: ~6-8 hours
- 2 hours: Redesign SegmentBuilder component with button-based UI
- 1.5 hours: Implement "Continue journey" vs "This is my destination" logic
- 1 hour: Add confirmation tick and post-save navigation
- 1 hour: Update validation and error display (show in context)
- 1 hour: Update display components (colored line buttons/chips)
- 30 min: Update tests
- 1 hour: Manual testing and polish

---

## Implementation Plan for Option B

### Overview

Implement button-based interface for route building that clearly represents the journey model: **STATION→LINE→STATION**.

### User Flow

**Step 1: Add Starting Station**
```
┌─────────────────────────────────────────┐
│ Add Starting Station                     │
├─────────────────────────────────────────┤
│ Station: [Southgate Underground ▼]      │
│                                          │
│ (No line selection yet - need 2 stations)│
└─────────────────────────────────────────┘
```

**Step 2: Select Line and Add Destination**
```
┌─────────────────────────────────────────┐
│ Journey from Southgate Underground       │
├─────────────────────────────────────────┤
│ Travel on line:                          │
│ ┌─────────────────┐                     │
│ │ 🚇 Piccadilly   │ ← Colored button   │
│ └─────────────────┘                     │
│                                          │
│ To station: [Leicester Square ▼]        │
│                                          │
│ What next?                               │
│ ┌────────────────┐ ┌─────────────────┐ │
│ │ + Continue     │ │ ✓ Destination   │ │
│ │   journey      │ │                 │ │
│ └────────────────┘ └─────────────────┘ │
└─────────────────────────────────────────┘
```

**If user clicks "✓ Destination"**:
- Set `line_id: null` for Leicester Square segment
- Show in segment list as "Destination"
- Enable "Save Segments" button

**If user clicks "+ Continue journey"**:
- Add Leicester Square with current line (Piccadilly)
- Show new form to add next segment
- Auto-fill line or allow change for interchange

**Step 3: Save with Confirmation**
```
┌─────────────────────────────────────────┐
│ [Save Segments ✓]  [Cancel]            │
│                                          │
│ After click:                             │
│ ✓ Segments saved!                       │
│ (Auto-scroll to "Active Times" section) │
└─────────────────────────────────────────┘
```

### Technical Implementation

#### Phase 1: Update Data Structures

**File**: `frontend/src/components/routes/SegmentBuilder.tsx`

```typescript
interface SegmentBuilderState {
  segments: Segment[];
  currentStation: Station | null;
  currentLine: Line | null;
  nextStation: Station | null;
  isAddingSegment: boolean;
  saveStatus: 'idle' | 'saving' | 'success' | 'error';
}

// Segment building rules:
// - Need currentStation + currentLine + nextStation to form valid segment
// - If user marks as destination: nextStation.line_id = null
// - If user continues: nextStation.line_id = currentLine.id (or changed line)
```

#### Phase 2: Component Redesign

**New Components to Create**:

1. **`LineButton.tsx`** - Colored button/chip for line selection
   ```tsx
   interface LineButtonProps {
     line: Line;
     selected: boolean;
     onClick: () => void;
   }
   ```

2. **`JourneyActionButtons.tsx`** - "Continue journey" vs "Destination" buttons
   ```tsx
   interface JourneyActionButtonsProps {
     onContinue: () => void;
     onDestination: () => void;
     disabled: boolean;
   }
   ```

3. **`SaveConfirmation.tsx`** - Success tick and auto-scroll
   ```tsx
   interface SaveConfirmationProps {
     show: boolean;
     onDismiss: () => void;
   }
   ```

**Modified Components**:

1. **`SegmentBuilder.tsx`**
   - Remove dropdown-based line selector
   - Add button-based line selection (show lines for current station)
   - Implement "Continue" vs "Destination" logic
   - Add save confirmation and navigation

2. **`SegmentCard.tsx`** / **`SegmentList.tsx`**
   - Update to show "Destination" badge for terminal segments
   - Show line as colored chip/badge instead of text

#### Phase 3: Validation Logic

**File**: `frontend/src/components/routes/SegmentBuilder.tsx`

```typescript
const validateSegmentBuilder = (state: SegmentBuilderState): string | null => {
  // Rule 1: Need at least 2 stations to form a journey
  if (state.segments.length === 0) {
    return "Add at least 2 stations to create a journey";
  }

  // Rule 2: Each intermediate segment must have a line_id
  for (let i = 0; i < state.segments.length - 1; i++) {
    if (!state.segments[i].line_id) {
      return `Segment ${i + 1} must have a line`;
    }
  }

  // Rule 3: Last segment can have null line_id (destination)
  // This is valid

  return null; // Valid
};
```

#### Phase 4: Save Flow with Confirmation

```typescript
const handleSave = async () => {
  setSaveStatus('saving');

  try {
    // Validate
    const error = validateSegmentBuilder(state);
    if (error) {
      toast.error(error);
      setSaveStatus('error');
      return;
    }

    // Save to backend
    await saveSegments(routeId, state.segments);

    // Show success
    setSaveStatus('success');

    // Auto-scroll to next section after 1 second
    setTimeout(() => {
      document.getElementById('active-times-section')?.scrollIntoView({
        behavior: 'smooth'
      });
    }, 1000);

  } catch (err) {
    setSaveStatus('error');
    toast.error('Failed to save segments. Please try again.');
  }
};
```

#### Phase 5: Error Display

Show validation errors inline, in context:

```tsx
{saveStatus === 'error' && validationError && (
  <Alert variant="destructive" className="mb-4">
    <AlertCircle className="h-4 w-4" />
    <AlertDescription>{validationError}</AlertDescription>
  </Alert>
)}
```

### Files to Modify

1. **`frontend/src/components/routes/SegmentBuilder.tsx`** - Main redesign
2. **`frontend/src/components/routes/SegmentCard.tsx`** - Update display
3. **`frontend/src/components/routes/SegmentList.tsx`** - Update display
4. **`frontend/src/components/routes/LineButton.tsx`** - New component
5. **`frontend/src/components/routes/JourneyActionButtons.tsx`** - New component
6. **`frontend/src/components/routes/SaveConfirmation.tsx`** - New component
7. **`frontend/src/pages/CreateRoute.tsx`** - Add ID to Active Times section

### Testing Checklist

- [ ] Can add starting station
- [ ] Can select line (only shows lines available at that station)
- [ ] Can add destination station
- [ ] "Continue journey" and "Destination" buttons work correctly
- [ ] Marking as destination sets `line_id: null`
- [ ] Continuing journey auto-fills line correctly
- [ ] Can add multiple segments (interchange routes)
- [ ] Save button shows confirmation tick
- [ ] Auto-scrolls to Active Times after successful save
- [ ] Validation errors show inline with context
- [ ] Can't save with invalid data (shows error)
- [ ] Line buttons show correct colors
- [ ] Works on mobile (buttons are tappable)

### Success Criteria

1. ✅ User understands journey model: STATION→LINE→STATION
2. ✅ Clear distinction between "continuing" vs "arriving at destination"
3. ✅ Terminal segments correctly have `line_id: null`
4. ✅ Visual feedback on save (confirmation tick)
5. ✅ Smooth transition to next section after save
6. ✅ Validation errors clear and actionable
7. ✅ Better mobile experience (large tap targets)

---

## Summary

**Analysis Complete**: ✅
**Defects Identified**: 4 real defects (1 was analysis error)
**User Decision**: Option B - Button-Based Interface
**Implementation Time**: 6-8 hours
**Documentation Updated**: `route_segment_data_model_analysis.md`
**Screenshot Captured**: `.playwright-mcp/route-builder-before-save.png`

**Next Steps**: Ready to implement Option B with button-based interface.
