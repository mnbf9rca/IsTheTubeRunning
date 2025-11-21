# External API Integration

## pydantic-tfl-api Integration

### Status
Active (Updated: Issue #200, pydantic-tfl-api v3.0.0)

### Context
The `pydantic-tfl-api` library provides type-safe TfL API client with Pydantic models. Version 3.0.0 introduced native async clients (`AsyncLineClient`, `AsyncStopPointClient`), eliminating the need for thread pool wrappers.

### Decision
Use native async clients from pydantic-tfl-api v3. Initialize with `AsyncLineClient(api_token=...)` and `AsyncStopPointClient(api_token=...)`. Call methods directly with `await client.MethodName(args)`. Responses are either `ApiError` or success objects with `.content` attribute containing Pydantic models.

### Consequences
**Easier:**
- Type-safe API responses (Pydantic models)
- Maintained library (don't need to write TfL client from scratch)
- Native async - no `run_in_executor()` boilerplate
- Standard async testing patterns (mock client methods with `AsyncMock`)
- Better performance (no thread pool overhead)

**More Difficult:**
- Must use v3.0.0+ of pydantic-tfl-api
- Async method signatures (must `await` all API calls)

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

## Multi-Mode Transport Support

### Status
Active

### Context
London has multiple transport modes beyond the Tube: Overground, DLR, Elizabeth Line, and Tram. Users need disruption information across all modes they use for their commutes, not just the Tube.

### Decision
Extend TfL API integration to support multiple transport modes. Methods `fetch_lines()`, `fetch_line_disruptions()`, and `fetch_station_disruptions()` now accept optional `modes` parameter (defaults to `["tube", "overground", "dlr", "elizabeth-line"]`). Each mode is queried separately via TfL API, and results are combined. Cache keys include mode list to prevent cache collision between different mode combinations. A new `fetch_available_modes()` method uses TfL's MetaModes API.

### Consequences
**Easier:**
- Comprehensive disruption coverage across all London transport modes
- Users get complete picture of their multi-mode commutes
- Frontend can filter by transport mode
- Extensible to future modes (Tram, Cable Car, etc.)

**More Difficult:**
- Multiple API calls per fetch operation (one per mode)
- More complex cache key management (must include modes)
- Increased test complexity (need to mock multiple mode responses)
- Higher API rate limit usage (4x calls by default vs single Tube call)

---

## StatusByIds over DisruptionByMode Endpoint

### Status
Active (Issue #121, 2025-01-12)

### Context
TfL API provides two endpoints for fetching disruption data: `/Line/Mode/{mode}/Disruption` and `/Line/{ids}/Status`. The Disruption endpoint returns only disruption objects, while Status provides `LineStatus` objects containing structured severity levels (0-20 scale) with `statusSeverity` and `statusSeverityDescription` fields. Initial implementation used Disruption endpoint which required hardcoded mapping from `closureText` strings ("severeDelays") to severity integers - this mapping was incomplete and incorrect.

### Decision
Use `/Line/{ids}/Status` endpoint (`StatusByIdsByPathIdsQueryDetail`) instead of `/Line/Mode/{mode}/Disruption`. Fetch line IDs via `fetch_lines()`, join with commas, make single Status API call per request. Extract `statusSeverity` integer directly from `LineStatus` objects - no mapping needed. When querying without `StartDate` and `EndDate` parameters, the TfL API automatically filters responses to only include currently active statuses.

### Consequences
**Easier:**
- No hardcoded severity mappings - API provides authoritative numeric values
- Complete disruption data (Status endpoint returns PlannedWork + RealTime simultaneously)
- Server-side temporal filtering - API returns only currently active statuses when StartDate/EndDate are omitted
- Structured severity scale (0-20) matches TfL's official MetaSeverity codes
- More accurate data (real-world testing showed Disruption endpoint missed planned closures)
- Both RealTime and PlannedWork disruptions included (Issue #208)
  - Note: The `ValidityPeriod.isNow` field indicates disruption category (RealTime vs PlannedWork), NOT temporal validity
  - We do NOT use `isNow` for filtering - TfL API handles temporal filtering server-side
  - The `isNow` field cannot be removed from `pydantic_tfl_api.ValidityPeriod` as it's defined by the external library

**More Difficult:**
- Requires fetching line IDs first (extra `fetch_lines()` call)
- Data structure is nested (`LineStatus.disruption` vs flat `Disruption`)
- Test mocks more complex (mock Line with nested LineStatus and ValidityPeriod)
- Different response shape requires updated test fixtures

---

## Capture Affected Routes Data from TfL API

### Status
Active (Issue #126, implemented 2025-11-13)

### Context
TfL API provides `affectedRoutes` with station sequences in disruption responses. Initial implementation discarded this data. Future inverted index (Issue #125) needs station-level data for accurate matching.

### Decision
Capture `affected_routes` field in `DisruptionResponse` containing route name, direction, and affected station NaPTAN codes. No route variant IDs (don't exist in Line.routes data).

### Consequences
**Easier:**
- Station-level disruption matching vs whole-line alerts
- Future inverted index implementation without schema migration

**More Difficult:**
- Larger response payloads with station lists

---

## Route Sequence Validation for Branch-Aware Paths

### Status
Active (Updated: 2025-11-10, Issue #57 - Added directional validation)

### Context
Some tube lines have branches where trains diverge to different destinations (e.g., Northern Line splits into Bank and Charing Cross branches at Camden Town). The previous validation approach used a graph-based BFS algorithm that would incorrectly allow travel between stations on different branches (e.g., Bank → Charing Cross on Northern line), since both stations technically serve the same line but aren't directly connected.

Additionally, TfL API's OrderedRoute object is directional (inbound/outbound), with stations listed in sequential order. The system must validate that user-specified routes follow the correct direction (Issue #57).

### Decision
Route validation uses Line.routes JSON data from TfL API to check if consecutive segments stay within the same route sequence **in the correct order**. The `_check_connection()` method validates that:
1. Both from_station and to_station exist in at least one common route sequence for the specified line
2. The stations appear in the correct order (to_station must come AFTER from_station in the route sequence)

This prevents:
- Cross-branch travel (e.g., Bank → Charing Cross on Northern line)
- Backwards travel (e.g., Piccadilly Circus → Arsenal when route sequence goes Arsenal → Piccadilly Circus)

**Bidirectional support**: Lines typically have both inbound and outbound route variants stored separately (e.g., "Brixton → Walthamstow" and "Walthamstow → Brixton"). The validation iterates through ALL route variants, so both directions work naturally by matching different route sequences.

**Performance**: Uses `stations.index()` for order validation, which is O(n) per route variant - same complexity as previous membership check. With typical route lengths of 20-60 stations and infrequent validation (only during route creation/editing), performance impact is negligible.

### Consequences
**Easier:**
- Accurate validation matching real-world TfL service patterns and direction
- Prevents impossible routes (cross-branch AND backwards travel)
- Better error messages (logged as "connection_found_but_wrong_direction" when direction is incorrect)
- Leverages existing TfL route sequence data (no additional API calls, no database schema changes)
- Frontend can filter available stations using `getNextStations()` to only show reachable stations
- No need to understand "inbound" vs "outbound" semantics - just check station order

**More Difficult:**
- Requires Line.routes JSON to be populated (depends on TfL API data)
- Validation fails for lines without route sequence data (graceful degradation with warning logs)
- More complex test fixtures (must include route sequences in test data)
- Slight performance overhead (iterating through route sequences + index lookups vs single graph lookup)

---

## Hub-Based Cross-Mode Interchange Validation

### Status
Active (Implemented: 2025-11-09, Issue #52)

### Context
Some London transport hubs serve multiple modes at the same physical location (e.g., Seven Sisters has both Overground and Victoria line). TfL represents these as separate stations with unique IDs, preventing users from creating valid cross-mode routes through the same physical interchange.

### Decision
Stations sharing the same `hub_naptan_code` are treated as **equivalent/interchangeable** for routing purposes. When validating connections between consecutive segments, the system retrieves all stations with the same hub code and accepts the route if any combination has a valid connection.

### Consequences
**Easier:**
- Realistic multi-mode routes (Overground → Tube → DLR, etc.)
- Users don't need to know which specific station ID to use at hubs
- Matches real-world interchange behavior

**More Difficult:**
- Additional database queries during validation
- More complex validation logic handling station combinations
- Test fixtures must include hub fields

**Limitations (YAGNI):**
- No support for Out-of-Station Interchanges (OSI)
- No walking time/distance validation
- Bus stop interchanges excluded (rail-based modes only)


---

## Hub NaPTAN Code Support as Station Identifiers

### Status
Active (Issue #65, implemented January 2025)

### Context
After implementing hub interchange validation (#52), users still had to choose between specific station IDs when specifying routes through hub interchanges. For example, at "Seven Sisters", users needed to know whether to use the Overground or Victoria line station ID, creating poor UX.

### Decision
Accept hub NaPTAN codes (e.g., `HUBSVS`) directly as `station_tfl_id` values in route segment requests. System automatically resolves hub codes to specific stations using line context, stores normalized station IDs in database, and returns canonical hub codes in API responses when available.

### Consequences

**Easier:**
- Improved UX: Users specify hub codes instead of choosing between multiple station IDs
- Consistent API responses: Hub-capable stations return canonical hub representation
- Backward compatible: Existing routes using station IDs continue to work
- Simple for frontend: Single identifier per interchange location

**More Difficult:**
- Additional resolution logic during station lookup
- Context-dependent behavior: Same hub code resolves differently based on line
- Must support two input formats (station IDs and hub codes)

### Related Decisions
- Builds on "Hub Interchange Validation" above

---

## Async Email Sending with aiosmtplib

### Status
Active (Issue #168, implemented 2025-01-17)

### Context
Email sending via SMTP is a network I/O operation that can block if the SMTP server is unreachable or slow. Initial implementation used Python's standard `smtplib` library wrapped in `asyncio.run_in_executor()` to prevent blocking the event loop. However, this approach still consumed thread pool threads and could hang indefinitely on unreachable hosts without a timeout configured.

### Decision
Use `aiosmtplib` library for truly async SMTP operations instead of wrapping synchronous `smtplib` in thread pool execution. Configure connection timeout (10 seconds default) to prevent indefinite hangs on unreachable SMTP hosts.

### Consequences
**Easier:**
- True async I/O - no thread pool blocking
- Better resource utilization in async FastAPI application
- Timeout protection prevents indefinite hangs (fails fast within 10 seconds)
- Native async integration with event loops
- Modern email message format (EmailMessage vs MIME)
- Simplified code (no `run_in_executor()` boilerplate)

**More Difficult:**
- Additional dependency (`aiosmtplib>=3.0.0`)
- Tests must mock async context managers (`__aenter__`/`__aexit__`)
- Different exception types (`aiosmtplib.SMTPException` vs `smtplib.SMTPException`)

---

## Line Validation Before TfL API Calls

### Status
Active (Issue #38)

### Context
`/api/v1/tfl/stations` accepted arbitrary `line_id` parameters and queried TfL API on cache miss, even for invalid lines. Malicious actors could spam non-existent line IDs, exhausting API quota and risking key blocking.

### Decision
Database-only for public endpoints: validate line exists before database query, never call TfL API. Returns 503 if graph uninitialized, 404 if line invalid or no stations. Added `skip_database_validation` parameter for graph building to allow controlled TfL API access.

### Consequences
**Easier:**
- Protects against API quota exhaustion
- Database whitelist of valid lines
- Consistent error responses (404/503)
- Clean API: `skip_database_validation` parameter makes intent explicit

**More Difficult:**
- Requires `/admin/tfl/build-graph` before queries work
- New TfL lines require manual graph rebuild
- Additional database query on cache miss (minimal: indexed lookup)

---

## Soft Delete with Partial Unique Index for Network Graph Rebuild

### Status
Active (Issue #230, implemented 2025-11-21)

### Context
When `build_station_graph()` rebuilt the network graph, it used hard DELETE to remove all existing `StationConnection` records before rebuilding. With PostgreSQL's default `READ COMMITTED` isolation level, the `flush()` operation made the deletion visible to concurrent transactions before the rebuild completed. This created a 30-60 second window where GET `/api/v1/tfl/network-graph` returned 503 errors because the table appeared empty to other sessions.

The issue was triggered by the startup task (PR #218) that automatically rebuilds the graph when Celery workers start. During the rebuild:
1. `delete(StationConnection)` + `flush()` at line 2578-2581 made table appear empty
2. 50+ TfL API calls to rebuild connections took 30-60 seconds
3. Concurrent GET requests found zero connections and returned 503
4. After `commit()`, new connections became visible

**Initial soft delete attempt failed** because the standard unique constraint required `flush()` to avoid violations when inserting new connections with the same keys. The flush() made UPDATE (soft delete) visible immediately while INSERT (new connections) only became visible after commit(), recreating the 503 window.

### Decision
Use soft delete pattern **with partial unique index** for network graph rebuilds. The `StationConnection` model already has a `deleted_at` field from `SoftDeleteMixin`. Implementation:

1. **Alembic migration (9888a309ff57)**: Replace standard unique constraint with partial unique index:
   ```sql
   CREATE UNIQUE INDEX uq_station_connection_active
   ON station_connections (from_station_id, to_station_id, line_id)
   WHERE deleted_at IS NULL;
   ```
2. **build_station_graph()**: Replace `delete(StationConnection)` with `update(StationConnection).where(deleted_at.is_(None)).values(deleted_at=NOW())` and **remove flush() call**
3. **get_network_graph()**: Add `.where(deleted_at.is_(None))` filter to all queries
4. **_connection_exists()**: Add `deleted_at.is_(None)` filter to only check active connections
5. **StationConnection model**: Update `__table_args__` to use `Index(..., unique=True, postgresql_where=text("deleted_at IS NULL"))`
6. **Test queries**: Update all test queries to filter out soft-deleted connections

**Why partial unique index is critical:**
- Standard unique constraint applies to ALL rows (including soft-deleted)
- Partial unique index only applies WHERE deleted_at IS NULL (active rows only)
- Allows soft-deleted and new records with same keys to coexist until commit
- Eliminates need for flush(), enabling true atomic commit

During rebuild:
- Old connections are marked `deleted_at=NOW()` (UPDATE, no flush)
- New connections are created with `deleted_at=NULL` (INSERT, no flush)
- Transaction commits atomically (old deleted, new active simultaneously)
- Concurrent queries see old connections until commit (no 503 window)

### Consequences
**Easier:**
- Zero downtime during graph rebuilds (eliminates 503 window)
- Old connections remain visible to concurrent queries until new ones commit
- Atomic transition from old to new graph data
- No flush() needed - true ACID transaction
- Startup rebuild can be re-enabled safely

**More Difficult:**
- Table accumulates soft-deleted records over time (one full graph per rebuild)
- All `StationConnection` queries must filter `deleted_at.is_(None)` for correctness
- Slightly larger table size (mitigated: daily rebuilds = ~365 old graphs per year = minimal)
- Requires partial index migration (PostgreSQL-specific feature)
- Future cleanup task may be needed if growth becomes an issue (deferred as YAGNI)

### Related Decisions
- Builds on "Admin Endpoint for Graph Building" (scheduled rebuilds via Celery)
- Uses soft delete pattern consistent with other models (ADR 06: User Management)
