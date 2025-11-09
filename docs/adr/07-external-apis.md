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

## Route Sequence Validation for Branch-Aware Paths

### Status
Active

### Context
Some tube lines have branches where trains diverge to different destinations (e.g., Northern Line splits into Bank and Charing Cross branches at Camden Town). The previous validation approach used a graph-based BFS algorithm that would incorrectly allow travel between stations on different branches (e.g., Bank → Charing Cross on Northern line), since both stations technically serve the same line but aren't directly connected.

### Decision
Route validation now uses Line.routes JSON data from TfL API to check if consecutive segments stay within the same route sequence. The `check_connection()` method validates that both the from_station and to_station exist in at least one common route sequence for the specified line. This prevents cross-branch travel while still allowing:
- Travel within a single branch (e.g., Bank → London Bridge on Northern via Bank)
- Travel on shared sections before/after splits (e.g., Edgware → Camden Town, which appears in all Northern line routes)
- Bidirectional travel (order doesn't matter, as long as both stations are in the same route sequence)

### Consequences
**Easier:**
- Accurate validation that matches real-world TfL service patterns
- Prevents impossible routes (cross-branch travel)
- Better error messages (explains when stations are on different branches)
- Leverages existing TfL route sequence data (no additional API calls)
- Frontend can filter available stations using `getNextStations()` to only show reachable stations

**More Difficult:**
- Requires Line.routes JSON to be populated (depends on TfL API data)
- Validation fails for lines without route sequence data (graceful degradation with warning logs)
- More complex test fixtures (must include route sequences in test data)
- Slight performance overhead (iterating through route sequences vs single graph lookup)
