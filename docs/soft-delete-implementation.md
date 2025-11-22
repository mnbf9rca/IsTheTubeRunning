# Soft Delete Implementation Guide

This document provides implementation patterns for soft deletes in the IsTheTubeRunning application.

**See Also:** [ADR 03: Soft Deletes](/docs/adr/03-database.md#soft-deletes) for the architectural decision and rationale.

## Overview

All models inherit the `deleted_at` timestamp column from `BaseModel`. When a record is soft-deleted, `deleted_at` is set to the current timestamp instead of removing the record from the database.

## Pattern 1: Soft Delete Operation

**Service Layer Implementation:**

```python
from sqlalchemy import func, update

async def delete_route(self, route_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Soft delete a route and cascade to all children."""
    # Verify ownership first
    await self.get_route_by_id(route_id, user_id)

    # Soft delete the route
    await self.db.execute(
        update(UserRoute)
        .where(
            UserRoute.id == route_id,
            UserRoute.deleted_at.is_(None),  # Prevent double-deletion
        )
        .values(deleted_at=func.now())
    )
    await self.db.commit()
```

**Key Points:**
- Use `update().values(deleted_at=func.now())` instead of `delete()`
- Always include `deleted_at.is_(None)` check to prevent double-deletion
- Use `func.now()` for server-side timestamp (consistent across distributed systems)

## Pattern 2: Application-Level Cascade

**Problem:** Database `CASCADE` deletes are hard deletes. We need soft-delete cascades.

**Solution:** Use `ondelete="RESTRICT"` on FK constraints and implement cascades in service layer.

```python
async def delete_route(self, route_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Soft delete route and cascade to all children."""
    # Verify ownership
    await self.get_route_by_id(route_id, user_id)

    # Cascade soft delete to all children BEFORE deleting parent
    await self.db.execute(
        update(UserRouteSegment)
        .where(
            UserRouteSegment.route_id == route_id,
            UserRouteSegment.deleted_at.is_(None),
        )
        .values(deleted_at=func.now())
    )

    await self.db.execute(
        update(UserRouteSchedule)
        .where(
            UserRouteSchedule.route_id == route_id,
            UserRouteSchedule.deleted_at.is_(None),
        )
        .values(deleted_at=func.now())
    )

    # ... cascade to other children (station_indexes, notification_preferences)

    # Finally soft delete the parent
    await self.db.execute(
        update(UserRoute)
        .where(
            UserRoute.id == route_id,
            UserRoute.deleted_at.is_(None),
        )
        .values(deleted_at=func.now())
    )

    await self.db.commit()
```

**Migration:**
```python
# Change CASCADE to RESTRICT
op.drop_constraint("fk_segments_route", "user_route_segments")
op.create_foreign_key(
    "fk_segments_route",
    "user_route_segments",
    "user_routes",
    ["route_id"],
    ["id"],
    ondelete="RESTRICT",  # Changed from CASCADE
)
```

**Benefits:**
- Explicit control over what gets soft-deleted
- Logging opportunities at each cascade step
- Prevents accidental hard deletes from DB-level cascades

## Pattern 3: Query Filtering

**ALL SELECT queries on soft-deletable models MUST filter by `deleted_at IS NULL`.**

```python
async def get_route_by_id(self, route_id: uuid.UUID, user_id: uuid.UUID) -> UserRoute:
    """Get route by ID with ownership check."""
    result = await self.db.execute(
        select(UserRoute)
        .where(
            UserRoute.id == route_id,
            UserRoute.user_id == user_id,
            UserRoute.deleted_at.is_(None),  # REQUIRED
        )
    )

    if not (route := result.scalar_one_or_none()):
        raise HTTPException(status_code=404, detail="Route not found")

    return route
```

**With Joins:**
```python
result = await self.db.execute(
    select(NotificationPreference)
    .join(UserRoute, NotificationPreference.route_id == UserRoute.id)
    .where(
        NotificationPreference.id == pref_id,
        UserRoute.user_id == user_id,
        UserRoute.deleted_at.is_(None),  # Filter joined table
        NotificationPreference.deleted_at.is_(None),  # Filter main table
    )
)
```

**Common Mistake:**
```python
# ❌ WRONG - missing deleted_at filter
select(UserRoute).where(UserRoute.id == route_id)

# ✅ CORRECT
select(UserRoute).where(
    UserRoute.id == route_id,
    UserRoute.deleted_at.is_(None),
)
```

## Pattern 4: Partial Unique Indexes

**Problem:** Unique constraints prevent reusing keys (e.g., sequence numbers) after soft delete.

**Solution:** Use partial unique index with `WHERE deleted_at IS NULL`.

**Migration:**
```python
def upgrade() -> None:
    # Drop standard unique constraint
    op.drop_constraint("uq_route_segment_sequence", "user_route_segments", type_="unique")

    # Create partial unique index
    op.create_index(
        "uq_route_segment_sequence_active",
        "user_route_segments",
        ["route_id", "sequence"],
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),  # Only enforce for active records
    )

def downgrade() -> None:
    op.drop_index("uq_route_segment_sequence_active", table_name="user_route_segments")
    op.create_unique_constraint(
        "uq_route_segment_sequence",
        "user_route_segments",
        ["route_id", "sequence"],
    )
```

**Model:**
```python
class UserRouteSegment(BaseModel):
    """Route segment with reusable sequence numbers."""

    __tablename__ = "user_route_segments"

    route_id: Mapped[uuid.UUID] = mapped_column(...)
    sequence: Mapped[int] = mapped_column(...)

    __table_args__ = (
        Index(
            "uq_route_segment_sequence_active",
            "route_id",
            "sequence",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
```

**Behavior:**
- Active records: Unique constraint enforced
- Soft-deleted records: Can have duplicate keys with active records
- Enables sequence number reuse after deletion

**Example:**
```
route_id | sequence | deleted_at
---------+----------+------------
123      | 0        | NULL        ← Active
123      | 1        | 2025-11-21  ← Soft deleted
123      | 1        | NULL        ← Active (reused sequence 1)
```

## Pattern 5: Model Documentation

Document soft delete behavior in model docstrings:

```python
class UserRoute(BaseModel):
    """
    User's commute route.

    Soft Delete: This model uses soft delete (deleted_at column from BaseModel).
    When deleting via user_route_service.delete_route(), all related entities
    (segments, schedules, station_indexes, notification_preferences) are also
    soft deleted. See Issue #233.
    """

    __tablename__ = "user_routes"
    # ...
```

## Checklist for Adding Soft Delete to a Model

- [ ] Model inherits from `BaseModel` (provides `deleted_at` column)
- [ ] All SELECT queries filter by `Model.deleted_at.is_(None)`
- [ ] Delete operations use `update().values(deleted_at=func.now())`
- [ ] Delete operations check `deleted_at.is_(None)` to prevent double-deletion
- [ ] Foreign keys use `ondelete="RESTRICT"`
- [ ] Application-level cascades implemented in service layer
- [ ] Unique constraints converted to partial indexes with `WHERE deleted_at IS NULL`
- [ ] Model docstring documents soft delete behavior
- [ ] Tests updated to verify soft delete (check `deleted_at` is set, not record removed)

## Examples

- **User Routes** (Issue #233):
  - Models: `UserRoute`, `UserRouteSegment`, `UserRouteSchedule`, `UserRouteStationIndex`, `NotificationPreference`
  - Services: `user_route_service.py`, `user_route_index_service.py`, `notification_preference_service.py`
  - Migration: `728def08ac79` (partial index), `3d846b7d1114` (FK RESTRICT)

- **Station Connections** (PR #231):
  - Model: `StationConnection`
  - Service: TBD
  - Migration: TBD

## Common Pitfalls

1. **Forgetting `deleted_at` filter in queries**
   - Symptom: Soft-deleted records appear in results
   - Fix: Add `.where(Model.deleted_at.is_(None))` to all SELECT queries

2. **Using standard unique constraints**
   - Symptom: Cannot reuse keys after soft delete (unique violation)
   - Fix: Convert to partial unique index with `WHERE deleted_at IS NULL`

3. **Database CASCADE on FK constraints**
   - Symptom: Children are hard-deleted when parent is soft-deleted
   - Fix: Change to `ondelete="RESTRICT"` and implement cascade in service

4. **Double-deletion attempts**
   - Symptom: Update affects 0 rows, silent failure
   - Fix: Include `deleted_at.is_(None)` in WHERE clause, handle 404

5. **Forgetting to cascade to children**
   - Symptom: Parent soft-deleted but children remain active (orphaned)
   - Fix: Explicitly soft-delete all children before parent in service layer

6. **Relationship loading includes soft-deleted records**
   - Symptom: Soft-deleted children appear in relationship collections (e.g., `route.segments`, `route.schedules`)
   - Explanation: SQLAlchemy relationships (like `route.segments`, `route.schedules`) don't automatically filter by `deleted_at IS NULL`. When using `selectinload()` or accessing lazy-loaded relationships, soft-deleted children will be included unless explicitly filtered.
   - Fix options:
     - Filter after loading: `active_segments = [s for s in route.segments if s.deleted_at is None]`
     - Query children directly with filter: `query = select(UserRouteSegment).where(UserRouteSegment.route_id == route_id)` then `add_active_filter(query, UserRouteSegment)`
     - Configure relationship with `primaryjoin` filtering (advanced, not recommended for simple cases)

## Helper Functions

To reduce repetitive code and prevent mistakes, use the soft delete helpers in `app/helpers/soft_delete_filters.py`.

### When to Use Helpers

**Always use helpers for consistency:**
- Use `add_active_filter()` instead of `.where(Model.deleted_at.is_(None))` for single models
- Use `add_active_filters()` instead of multiple `.where()` clauses for joins
- Use `soft_delete()` instead of manual `update().where().values(deleted_at=func.now())` patterns

**Benefits:**
- **DRY (Don't Repeat Yourself)**: Single source of truth for filtering logic
- **Consistency**: All code uses the same pattern, easier to review and maintain
- **Safety**: `soft_delete()` requires at least one WHERE clause to prevent accidental mass deletions
- **Type Safety**: Helpers maintain SQLAlchemy type information
- **Readability**: Intent is clearer (`add_active_filter(query, Model)` vs `.where(Model.deleted_at.is_(None))`)

**When NOT to use:**
- Non-soft-deletable models (models without `deleted_at` column)
- When you intentionally need to query deleted records for admin/audit purposes
- Complex relationship queries where `primaryjoin` filtering is more appropriate

### Query Filtering

```python
from app.helpers.soft_delete_filters import add_active_filter, add_active_filters

# Filter single model
query = select(UserRoute).where(UserRoute.user_id == user_id)
query = add_active_filter(query, UserRoute)

# Filter multiple models in a join
query = (
    select(NotificationPreference)
    .join(UserRoute)
    .where(NotificationPreference.route_id == route_id)
)
query = add_active_filters(query, NotificationPreference, UserRoute)
```

### Soft Delete Execution

```python
from app.helpers.soft_delete_filters import soft_delete

# Soft delete an entity
await soft_delete(db, UserRoute, UserRoute.id == route_id)

# With multiple conditions
await soft_delete(
    db,
    UserRouteSegment,
    UserRouteSegment.route_id == route_id,
    UserRouteSegment.sequence > 5,
)
```

### Testing Helpers

```python
from tests.helpers.soft_delete_assertions import (
    assert_soft_deleted,
    assert_cascade_soft_deleted,
    assert_not_in_api_list,
    assert_api_returns_404,
)

# Verify entity is soft deleted
await assert_soft_deleted(db, UserRoute, route_id)

# Verify cascade deletion
await assert_cascade_soft_deleted(
    db,
    route_id,
    {
        UserRouteSegment: UserRouteSegment.route_id,
        UserRouteSchedule: UserRouteSchedule.route_id,
    }
)

# Verify API visibility
await assert_not_in_api_list(client, "/routes", route_id, auth_headers)
await assert_api_returns_404(client, f"/routes/{route_id}", auth_headers)
```
