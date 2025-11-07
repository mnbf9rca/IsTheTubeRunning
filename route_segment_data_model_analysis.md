# Route Segment Data Model Analysis

**Date**: 2025-11-07
**Issue**: Data model mismatch between conceptual route representation and database schema

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
- Requires schema migration
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
- Need to update all existing routes in migration
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
- Major schema migration
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

---

## Recommendation

**Option 1: Make `line_id` Nullable** (Model B)

**Rationale**:
1. **Minimal disruption**: Single column constraint change
2. **Clear semantics**: NULL explicitly means "journey ends here"
3. **Matches user intent**: Line only needed when departing from a station
4. **Proper data modeling**: Don't store meaningless values

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
   - Can we safely set last segment's line_id to NULL in migration?

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
7. [ ] Test migration with sample data

### If Option 2 (Connection model):
1. [ ] Design new schema in detail
2. [ ] Write migration strategy
3. [ ] Plan phased rollout
4. [ ] Update all affected code

### If Option 3 (Keep as-is):
1. [ ] Document the quirk
2. [ ] Accept technical debt
3. [ ] Complete UX hiding (already done)
