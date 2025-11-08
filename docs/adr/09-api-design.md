# API Design

## KISS Analytics Approach

### Status
Active

### Context
Admin dashboard needs user counts, route stats, notification stats, and growth metrics. Could create multiple specialized endpoints or single comprehensive endpoint.

### Decision
Single comprehensive engagement endpoint (`GET /admin/analytics/engagement`) instead of multiple specialized analytics APIs. Returns four metric categories in one call: user counts, route stats, notification stats, growth/retention metrics. Can add specialized endpoints later if needed.

### Consequences
**Easier:**
- Reduces API surface area
- Simplifies frontend integration (one API call)
- Follows YAGNI principle (don't build what we don't need yet)
- Easier to add specialized endpoints later if traffic becomes concern

**More Difficult:**
- Single endpoint returns more data than needed if only one metric is desired
- Cannot cache individual metrics separately (cache whole response or nothing)
- Larger response payload

---

## TfL IDs in API Surface, UUIDs in Database

### Status
Active

### Context
Route and validation APIs need to reference stations and lines. Database uses UUID primary keys for performance and consistency, but external consumers (frontend, API clients) interact with TfL's public identifiers (e.g., 'victoria' for Victoria line, '940GZZLUOXC' for Oxford Circus station).

**Options considered:**
1. Expose database UUIDs in API - requires clients to know internal IDs
2. Use TfL IDs everywhere including database - requires changing primary keys
3. **Use TfL IDs in API, UUIDs in database with translation layer**

### Decision
API endpoints accept and return TfL IDs (`station_tfl_id`, `line_tfl_id`) while database maintains UUID primary keys and foreign keys. Service layer translates between TfL IDs (API) and UUIDs (database).

**Implementation:**
- Request schemas: `SegmentRequest` uses `station_tfl_id: str` and `line_tfl_id: str`
- Response schemas: `SegmentResponse` returns `station_tfl_id: str` and `line_tfl_id: str`
- Service layer: `RouteService` and `TfLService` translate TfL IDs → UUIDs before database operations
- Lookup methods: `TfLService.get_station_by_tfl_id()` and `TfLService.get_line_by_tfl_id()` with indexed queries
- Model properties: `RouteSegment.station_tfl_id` and `RouteSegment.line_tfl_id` properties access related objects
- Exception handling: Invalid TfL IDs raise HTTPException 404 with helpful error messages

### Consequences
**Easier:**
- **User-friendly API**: Clients use meaningful identifiers ('victoria', 'oxford-circus') instead of opaque UUIDs
- **Frontend simplicity**: No need to maintain UUID mappings - TfL IDs are self-documenting
- **External integration**: Third parties can use TfL's public IDs without learning our internal schema
- **Debugging**: Error messages and logs show recognizable station/line names via TfL IDs
- **No migrations needed**: Database schema remains unchanged (zero risk to data integrity)
- **Validation clarity**: 404 errors immediately indicate invalid TfL IDs before validation runs

**More Difficult:**
- **Translation overhead**: Extra database queries to convert TfL IDs → UUIDs (mitigated by indexed lookups and eager loading)
- **Breaking API change**: Existing clients using UUIDs must update (acceptable for hobby project)
- **Property access requirements**: Response serialization requires eager-loading Station/Line relationships
- **Dual identifier maintenance**: Models have both UUID PKs and TfL ID unique constraints

**Performance notes:**
- Station and Line tables have unique indexes on `tfl_id` columns (fast lookups)
- No Redis caching for ID translations (YAGNI principle - indexed lookups are fast enough)
- Queries use `selectinload()` to eager-load relationships, avoiding N+1 queries
