"""
Test assertion helpers for verifying soft delete behavior.

These utilities provide reusable assertions for testing soft delete implementation,
reducing code duplication and making tests more readable.

Usage examples:
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
"""

import uuid

from app.models.base import BaseModel
from httpx import AsyncClient
from sqlalchemy import UUID, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute


async def assert_soft_deleted(
    db: AsyncSession,
    model: type[BaseModel],
    entity_id: uuid.UUID,
    *,
    message: str | None = None,
) -> None:
    """
    Assert that an entity has been soft deleted (deleted_at is not None).

    Args:
        db: Database session
        model: Model class to check
        entity_id: UUID of the entity to check
        message: Optional custom assertion message

    Raises:
        AssertionError: If entity is not soft deleted or doesn't exist

    Example:
        await assert_soft_deleted(db, UserRoute, route_id)
    """
    result = await db.execute(select(model).where(model.id == entity_id))
    entity = result.scalar_one_or_none()

    if message is None:
        message = f"{model.__name__} {entity_id} should be soft deleted"

    assert entity is not None, f"{model.__name__} {entity_id} does not exist"
    assert entity.deleted_at is not None, message


async def assert_not_soft_deleted(
    db: AsyncSession,
    model: type[BaseModel],
    entity_id: uuid.UUID,
    *,
    message: str | None = None,
) -> None:
    """
    Assert that an entity is NOT soft deleted (deleted_at is None).

    Args:
        db: Database session
        model: Model class to check
        entity_id: UUID of the entity to check
        message: Optional custom assertion message

    Raises:
        AssertionError: If entity is soft deleted or doesn't exist

    Example:
        await assert_not_soft_deleted(db, NotificationLog, log_id)
    """
    result = await db.execute(select(model).where(model.id == entity_id))
    entity = result.scalar_one_or_none()

    if message is None:
        message = f"{model.__name__} {entity_id} should NOT be soft deleted"

    assert entity is not None, f"{model.__name__} {entity_id} does not exist"
    assert entity.deleted_at is None, message


async def assert_cascade_soft_deleted(
    db: AsyncSession,
    parent_id: uuid.UUID,
    related_models: dict[type[BaseModel], InstrumentedAttribute[UUID]],
    *,
    message_prefix: str = "Related entities should be soft deleted",
) -> None:
    """
    Assert that all related entities were cascaded soft deleted.

    Verifies that when a parent entity is soft deleted, all related child
    entities (identified by foreign key) are also soft deleted.

    Args:
        db: Database session
        parent_id: UUID of the parent entity
        related_models: Mapping of {ChildModel: foreign_key_column}
        message_prefix: Prefix for assertion messages

    Raises:
        AssertionError: If any related entity is not soft deleted

    Example:
        await assert_cascade_soft_deleted(
            db,
            route_id,
            {
                UserRouteSegment: UserRouteSegment.route_id,
                UserRouteSchedule: UserRouteSchedule.route_id,
                NotificationPreference: NotificationPreference.route_id,
            }
        )
    """
    for model, fk_column in related_models.items():
        result = await db.execute(select(model).where(fk_column == parent_id))
        entities = result.scalars().all()

        for entity in entities:
            assert entity.deleted_at is not None, (
                f"{message_prefix}: {model.__name__} {entity.id} should be soft deleted"
            )


async def assert_not_in_api_list(
    client: AsyncClient,
    endpoint: str,
    entity_id: uuid.UUID,
    headers: dict[str, str],
    *,
    id_field: str = "id",
    message: str | None = None,
) -> None:
    """
    Assert that a deleted entity does not appear in API list response.

    Args:
        client: HTTP client for API requests
        endpoint: API endpoint to call (e.g., "/routes")
        entity_id: UUID of the entity that should not appear
        headers: Request headers (typically auth headers)
        id_field: Name of the ID field in response JSON (default: "id")
        message: Optional custom assertion message

    Raises:
        AssertionError: If entity appears in list or request fails

    Example:
        await assert_not_in_api_list(
            client,
            "/routes",
            deleted_route_id,
            auth_headers,
        )
    """
    response = await client.get(endpoint, headers=headers)
    assert response.status_code == 200, f"API request failed: {response.text}"

    data = response.json()
    entity_ids = [item[id_field] for item in data]

    if message is None:
        message = f"Entity {entity_id} should not appear in {endpoint} list"

    assert str(entity_id) not in entity_ids, message


async def assert_api_returns_404(
    client: AsyncClient,
    endpoint: str,
    headers: dict[str, str],
    *,
    message: str | None = None,
) -> None:
    """
    Assert that an API endpoint returns 404 Not Found.

    Typically used to verify that deleted entities cannot be accessed by ID.

    Args:
        client: HTTP client for API requests
        endpoint: API endpoint to call (e.g., "/routes/123")
        headers: Request headers (typically auth headers)
        message: Optional custom assertion message

    Raises:
        AssertionError: If response is not 404

    Example:
        await assert_api_returns_404(
            client,
            f"/routes/{deleted_route_id}",
            auth_headers,
        )
    """
    response = await client.get(endpoint, headers=headers)

    if message is None:
        message = f"Endpoint {endpoint} should return 404"

    assert response.status_code == 404, message
