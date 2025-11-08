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

## Nullable Route Segment line_id

### Status
Active (Implemented 2025-11-07)

### Context
Users create routes by selecting stations and lines conceptually as "From Station A, take Line X to Station B". The database initially required `line_id` for every segment, but the destination segment has no outgoing line - the journey terminates there. This created a mismatch:
- Validation only uses `segment[i].line_id` to check connections to `segment[i+1]`
- The last segment's `line_id` is never used in validation
- Storing a line for the destination is semantically meaningless

Four options considered:
1. **Nullable line_id**: Allow NULL for destination (chosen)
2. **Connection model**: Restructure to `{from_station, line, to_station}` per segment (too disruptive)
3. **Status quo**: Keep workaround, store redundant data (technical debt)
4. **Sentinel line**: Create fake "TERMINATES" line (pollutes domain model)

### Decision
Make `route_segments.line_id` nullable. NULL explicitly means "journey terminates here" (no outgoing line). Only the final segment can have NULL `line_id` - intermediate segments must have a line to travel on.

Backend validation enforces this rule. Frontend automatically sets the last segment's `line_id` to NULL when saving routes.

### Consequences
**Easier:**
- Data model matches conceptual model ("From A on Line X to B" followed by "Arrive at C")
- Semantically correct: NULL means "no value" (standard SQL pattern)
- No redundant data stored (DRY principle)
- Clear validation rules prevent misuse
- No fake/polluting data in domain model
- Minimal disruption (single column constraint change)

**More Difficult:**
- Need NULL checks in validation and display logic
- Slightly more complex queries (must handle NULL case)
- Nullable fields require careful handling in TypeScript (but type system helps)

### Implementation Details

**Database:**
- Migration `e5dfdd8388bc` makes `route_segments.line_id` nullable (UUID column)
- Database constraint: `line_id uuid NULL`

**Model Property:**
- `RouteSegment.line_tfl_id` property returns `str | None`
- Returns `self.line.tfl_id if self.line else None` to handle NULL line_id gracefully

**API Schemas (Updated 2025-11-08):**
- `SegmentRequest.line_tfl_id: str | None` - accepts NULL for destination segments
- `SegmentResponse.line_tfl_id: str | None` - returns NULL when line_id is NULL
- `RouteSegmentRequest.line_tfl_id: str | None` - validation schema accepts NULL
- Field descriptions document: "NULL means destination segment (no onward travel)"

**Validation Rules:**
- Minimum 2 segments required (origin --line--> destination)
- Segments 0 to len-2 (all except last) MUST have non-null line_tfl_id
- Segment len-1 (final segment) MAY have NULL line_tfl_id (optional)
- Validation error message: "Segment {i} must have a line_tfl_id. Only the final segment (destination) can have NULL line_tfl_id."
- Implemented in `TfLService.validate_route()` (backend/app/services/tfl_service.py)

**Service Layer Translation:**
- `RouteService.upsert_segments()` conditionally fetches line only if line_tfl_id is not None
- `line = await self.tfl_service.get_line_by_tfl_id(seg.line_tfl_id) if seg.line_tfl_id else None`
- Sets `line_id=line.id if line else None` when creating RouteSegment instances
- `RouteService._validate_route_segments()` already handles nullable line_tfl_id correctly

**Test Coverage:**
- `test_validate_route_with_null_destination_line_id` - validates NULL on final segment (valid)
- `test_validate_route_with_null_intermediate_line_id` - validates NULL on intermediate segment (invalid)
- `test_upsert_segments_with_null_destination_line` - API integration test with NULL destination
- All tests achieve 100% coverage on nullable line_tfl_id logic
