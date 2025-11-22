"""
Soft delete helper functions for consistent filtering and deletion.

These utilities help avoid common mistakes when implementing soft delete pattern:
- Missing deleted_at filters in queries
- Inconsistent soft delete update statements
- Verbose and error-prone manual filtering

Usage examples:
    # Filtering queries
    query = select(UserRoute).where(UserRoute.user_id == user_id)
    query = add_active_filter(query, UserRoute)

    # Multiple models in a join
    query = (
        select(NotificationPreference)
        .join(UserRoute)
        .where(NotificationPreference.route_id == route_id)
    )
    query = add_active_filters(query, NotificationPreference, UserRoute)

    # Soft deleting
    await soft_delete(db, UserRoute, UserRoute.id == route_id)
"""

from typing import TypeVar

from sqlalchemy import ColumnElement, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.base import BaseModel

# TypeVar for maintaining type safety across query transformations
T = TypeVar("T")


def add_active_filter(  # noqa: UP047
    query: Select[T],  # type: ignore[type-var]
    model: type[BaseModel],
) -> Select[T]:  # type: ignore[type-var]
    """
    Add deleted_at IS NULL filter to a query for a single model.

    Args:
        query: SQLAlchemy select query
        model: Model class that inherits from BaseModel

    Returns:
        Query with deleted_at filter added

    Example:
        query = select(UserRoute).where(UserRoute.user_id == user_id)
        query = add_active_filter(query, UserRoute)
        # Equivalent to: query.where(UserRoute.deleted_at.is_(None))
    """
    return query.where(model.deleted_at.is_(None))


def add_active_filters(  # noqa: UP047
    query: Select[T],  # type: ignore[type-var]
    *models: type[BaseModel],
) -> Select[T]:  # type: ignore[type-var]
    """
    Add deleted_at IS NULL filters to a query for multiple models.

    Useful when joining multiple tables that all use soft delete.

    Args:
        query: SQLAlchemy select query
        *models: Model classes that inherit from BaseModel

    Returns:
        Query with deleted_at filters added for all models

    Example:
        query = (
            select(NotificationPreference)
            .join(UserRoute)
            .where(NotificationPreference.route_id == route_id)
        )
        query = add_active_filters(query, NotificationPreference, UserRoute)
        # Equivalent to:
        # query.where(
        #     NotificationPreference.deleted_at.is_(None),
        #     UserRoute.deleted_at.is_(None),
        # )
    """
    for model in models:
        query = add_active_filter(query, model)
    return query


async def soft_delete(
    db: AsyncSession,
    model: type[BaseModel],
    *where_clauses: ColumnElement[bool],
) -> None:
    """
    Perform soft delete by setting deleted_at to current timestamp.

    This helper standardizes the soft delete pattern and ensures consistency
    across all services. Always includes deleted_at.is_(None) in the WHERE
    clause to prevent updating already-deleted records.

    Args:
        db: Database session
        model: Model class to soft delete
        *where_clauses: Additional WHERE conditions (e.g., model.id == some_id).
                       At least one WHERE clause is required to prevent
                       accidental mass deletion.

    Raises:
        ValueError: If no where_clauses are provided (prevents accidental
                   mass soft-deletion of all records)

    Example:
        # Delete a single route
        await soft_delete(db, UserRoute, UserRoute.id == route_id)

        # Delete multiple segments
        await soft_delete(
            db,
            UserRouteSegment,
            UserRouteSegment.route_id == route_id,
        )

    Note:
        This does NOT call db.commit() - caller must commit the transaction.
    """
    if not where_clauses:
        msg = (
            f"soft_delete requires at least one WHERE clause to prevent "
            f"accidental mass deletion. Attempted to delete all {model.__name__} records."
        )
        raise ValueError(msg)

    await db.execute(
        update(model)
        .where(
            *where_clauses,
            model.deleted_at.is_(None),
        )
        .values(deleted_at=func.now())
    )


def is_soft_deleted(entity: BaseModel) -> bool:
    """
    Check if an entity is soft deleted.

    Args:
        entity: Entity instance to check

    Returns:
        True if entity has deleted_at set, False otherwise

    Example:
        route = await db.get(UserRoute, route_id)
        if is_soft_deleted(route):
            raise HTTPException(status_code=404, detail="Route not found")
    """
    return entity.deleted_at is not None
