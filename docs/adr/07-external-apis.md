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
Use `/Line/{ids}/Status` endpoint (`StatusByIdsByPathIdsQueryDetail`) instead of `/Line/Mode/{mode}/Disruption`. Fetch line IDs via `fetch_lines()`, join with commas, make single Status API call per request. Extract `statusSeverity` integer directly from `LineStatus` objects - no mapping needed. Filter disruptions by `validityPeriods[].isNow == true` for currently active issues.

### Consequences
**Easier:**
- No hardcoded severity mappings - API provides authoritative numeric values
- Complete disruption data (Status endpoint returns PlannedWork + RealTime simultaneously)
- Time validity filtering via `isNow` flag (know which disruptions are currently active)
- Structured severity scale (0-20) matches TfL's official MetaSeverity codes
- More accurate data (real-world testing showed Disruption endpoint missed planned closures)

**More Difficult:**
- Requires fetching line IDs first (extra `fetch_lines()` call)
- Data structure is nested (`LineStatus.disruption` vs flat `Disruption`)
- Test mocks more complex (mock Line with nested LineStatus and ValidityPeriod)
- Different response shape requires updated test fixtures

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
