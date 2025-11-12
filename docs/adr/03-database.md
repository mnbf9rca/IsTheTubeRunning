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
Users conceptually create routes as "From Station A, take Line X to Station B". Database initially required `line_id` for every segment, but destination segments have no outgoing line - storing one is semantically meaningless. Validation only uses `segment[i].line_id` to check connections to `segment[i+1]`, so the last segment's line is never used.

### Decision
Make `route_segments.line_id` nullable. NULL explicitly means "journey terminates here". Only final segment can have NULL - intermediate segments must have a line. Backend validation enforces this. Rejected alternatives: connection model (too disruptive), sentinel "TERMINATES" line (pollutes domain), status quo (technical debt).

### Consequences
**Easier:**
- Data model matches conceptual model
- Semantically correct (NULL = no value)
- No redundant data (DRY principle)
- Minimal disruption (single column constraint)

**More Difficult:**
- NULL checks in validation and display logic
- Nullable fields require careful TypeScript handling

---

## Hub NaPTAN Code for Cross-Mode Interchanges

### Status
Active (Implemented 2025-11-09, Issues #50-55)

### Context
TfL represents interchange stations with multiple transport modes as separate stations with unique IDs (e.g., Seven Sisters has distinct IDs for Overground and Victoria line). Users need to create routes that change between modes at these physical locations. TfL provides a `hubNaptanCode` field linking related stations at the same physical interchange.

### Decision
Add two nullable fields to the `stations` table:
- `hub_naptan_code`: TfL's hub identifier linking stations at the same physical location (indexed for fast lookups)
- `hub_common_name`: User-friendly display name for the hub

Fields are nullable because only major interchange stations with multiple modes have hub codes.

### Consequences
**Easier:**
- Route validation recognizes cross-mode interchanges at the same physical location
- Users can create journeys changing between modes (e.g., Overground → Tube)
- Improved UX with hub common names instead of separate station names
- Flexible design accommodates both hub and non-hub stations

**More Difficult:**
- Route validation must check both direct connections and hub-based connections
- Hub data must be populated from TfL API
- Must handle NULL values in validation and display logic
