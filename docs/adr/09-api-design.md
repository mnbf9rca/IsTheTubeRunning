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
