"""UserRoute management service."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.route import UserRoute, UserRouteSchedule, UserRouteSegment
from app.models.tfl import Line, Station
from app.schemas.routes import (
    CreateRouteRequest,
    CreateScheduleRequest,
    SegmentRequest,
    UpdateRouteRequest,
    UpdateScheduleRequest,
    UpdateSegmentRequest,
)
from app.schemas.tfl import RouteSegmentRequest
from app.services.route_index_service import RouteIndexService
from app.services.tfl_service import TfLService

# Constants
MIN_ROUTE_SEGMENTS = 2


class RouteService:
    """Service for managing user routes."""

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the route service.

        Args:
            db: Database session
        """
        self.db = db
        self.tfl_service = TfLService(db)

    async def get_route_by_id(
        self,
        route_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        load_relationships: bool = False,
    ) -> UserRoute:
        """
        Get a route by ID with ownership validation.

        Args:
            route_id: UserRoute UUID
            user_id: User UUID (for ownership check)
            load_relationships: Whether to eager load segments and schedules

        Returns:
            UserRoute object

        Raises:
            HTTPException: 404 if route not found or doesn't belong to user
        """
        query = select(UserRoute).where(
            UserRoute.id == route_id,
            UserRoute.user_id == user_id,
        )

        if load_relationships:
            query = query.options(
                selectinload(UserRoute.segments).selectinload(UserRouteSegment.station),
                selectinload(UserRoute.segments).selectinload(UserRouteSegment.line),
                selectinload(UserRoute.schedules),
            )

        result = await self.db.execute(query)

        if not (route := result.scalar_one_or_none()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="UserRoute not found.",
            )

        return route

    async def list_routes(self, user_id: uuid.UUID) -> list[UserRoute]:
        """
        List all routes for a user.

        Args:
            user_id: User UUID

        Returns:
            List of routes with segments and schedules loaded
        """
        result = await self.db.execute(
            select(UserRoute)
            .where(UserRoute.user_id == user_id)
            .options(
                selectinload(UserRoute.segments).selectinload(UserRouteSegment.station),
                selectinload(UserRoute.segments).selectinload(UserRouteSegment.line),
                selectinload(UserRoute.schedules),
            )
            .order_by(UserRoute.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_route(
        self,
        user_id: uuid.UUID,
        request: CreateRouteRequest,
    ) -> UserRoute:
        """
        Create a new route.

        Args:
            user_id: User UUID
            request: UserRoute creation request

        Returns:
            Created route
        """
        route = UserRoute(
            user_id=user_id,
            name=request.name,
            description=request.description,
            active=request.active,
            timezone=request.timezone,
        )

        self.db.add(route)
        await self.db.commit()
        await self.db.refresh(route)

        return route

    async def update_route(
        self,
        route_id: uuid.UUID,
        user_id: uuid.UUID,
        request: UpdateRouteRequest,
    ) -> UserRoute:
        """
        Update route metadata.

        Args:
            route_id: UserRoute UUID
            user_id: User UUID (for ownership check)
            request: Update request

        Returns:
            Updated route

        Raises:
            HTTPException: 404 if route not found
        """
        route = await self.get_route_by_id(route_id, user_id)

        # Update only provided fields
        if request.name is not None:
            route.name = request.name
        if request.description is not None:
            route.description = request.description
        if request.active is not None:
            route.active = request.active
        if request.timezone is not None:
            route.timezone = request.timezone

        await self.db.commit()
        await self.db.refresh(route)

        return route

    async def delete_route(self, route_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """
        Delete a route (and all its segments and schedules via CASCADE).

        Args:
            route_id: UserRoute UUID
            user_id: User UUID (for ownership check)

        Raises:
            HTTPException: 404 if route not found
        """
        route = await self.get_route_by_id(route_id, user_id)

        await self.db.delete(route)
        await self.db.commit()

    async def upsert_segments(
        self,
        route_id: uuid.UUID,
        user_id: uuid.UUID,
        segments: list[SegmentRequest],
    ) -> list[UserRouteSegment]:
        """
        Replace all segments for a route with validation.

        This validates the route before saving. If validation fails,
        no changes are made.

        Args:
            route_id: UserRoute UUID
            user_id: User UUID (for ownership check)
            segments: List of segments to set

        Returns:
            List of created segments

        Raises:
            HTTPException: 404 if route not found, 400 if validation fails
        """
        # Verify ownership
        await self.get_route_by_id(route_id, user_id)

        # Validate the route using TfL service
        await self._validate_segments(segments)

        # Wrap delete + create in a transaction to ensure atomicity
        try:
            # Delete existing segments
            await self.db.execute(sql_delete(UserRouteSegment).where(UserRouteSegment.route_id == route_id))

            # Create new segments - translate TfL IDs (or hub codes) to UUIDs
            new_segments = []
            for seg in segments:
                # Resolve station (supports both station TfL IDs and hub codes)
                # Pass line context for hub resolution
                station = await self.tfl_service.resolve_station_or_hub(seg.station_tfl_id, seg.line_tfl_id)
                # Line is optional for destination segments (NULL line_tfl_id)
                line = await self.tfl_service.get_line_by_tfl_id(seg.line_tfl_id) if seg.line_tfl_id else None

                new_segments.append(
                    UserRouteSegment(
                        route_id=route_id,
                        sequence=seg.sequence,
                        station_id=station.id,
                        line_id=line.id if line else None,
                    )
                )

            self.db.add_all(new_segments)
            await self.db.flush()  # Flush to make segments available for index building

            # Build route station index (part of same transaction)
            index_service = RouteIndexService(self.db)
            await index_service.build_route_station_index(route_id, auto_commit=False)

            await self.db.commit()

            # Reload with relationships to support station_tfl_id and line_tfl_id properties
            result = await self.db.execute(
                select(UserRouteSegment)
                .where(UserRouteSegment.route_id == route_id)
                .options(selectinload(UserRouteSegment.station), selectinload(UserRouteSegment.line))
                .order_by(UserRouteSegment.sequence)
            )
            return list(result.scalars().all())
        except Exception:
            await self.db.rollback()
            raise

    async def update_segment(
        self,
        route_id: uuid.UUID,
        user_id: uuid.UUID,
        sequence: int,
        request: UpdateSegmentRequest,
    ) -> UserRouteSegment:
        """
        Update a single segment and validate the entire route.

        Args:
            route_id: UserRoute UUID
            user_id: User UUID (for ownership check)
            sequence: Sequence number of segment to update
            request: Update request

        Returns:
            Updated segment

        Raises:
            HTTPException: 404 if route or segment not found, 400 if validation fails
        """
        # Verify ownership and load all segments
        route = await self.get_route_by_id(route_id, user_id, load_relationships=True)

        # Find the segment to update
        segment = next((s for s in route.segments if s.sequence == sequence), None)
        if not segment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Segment with sequence {sequence} not found.",
            )

        # Update fields - translate TfL IDs (or hub codes) to UUIDs
        if request.station_tfl_id is not None:
            # Determine line context for hub resolution
            # Use new line if provided, otherwise use existing segment's line
            line_context = (
                request.line_tfl_id
                if request.line_tfl_id is not None
                else segment.line.tfl_id
                if segment.line
                else None
            )
            station = await self.tfl_service.resolve_station_or_hub(request.station_tfl_id, line_context)
            segment.station_id = station.id
        if request.line_tfl_id is not None:
            line = await self.tfl_service.get_line_by_tfl_id(request.line_tfl_id)
            segment.line_id = line.id

        # Validate the entire route with the update
        await self._validate_route_segments(route.segments)

        await self.db.flush()  # Flush to make changes available for index building

        # Rebuild route station index (part of same transaction)
        index_service = RouteIndexService(self.db)
        await index_service.build_route_station_index(route_id, auto_commit=False)

        await self.db.commit()

        # Expire the segment to ensure fresh data is loaded
        await self.db.refresh(segment, ["station", "line"])

        return segment

    async def delete_segment(
        self,
        route_id: uuid.UUID,
        user_id: uuid.UUID,
        sequence: int,
    ) -> None:
        """
        Delete a segment and resequence remaining segments.

        Args:
            route_id: UserRoute UUID
            user_id: User UUID (for ownership check)
            sequence: Sequence number of segment to delete

        Raises:
            HTTPException: 404 if route or segment not found, 400 if would leave <2 segments
        """
        # Verify ownership and load segments
        route = await self.get_route_by_id(route_id, user_id, load_relationships=True)

        # Check minimum segment requirement
        if len(route.segments) <= MIN_ROUTE_SEGMENTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete segment. UserRoute must have at least 2 segments.",
            )

        # Find and delete the segment
        segment = next((s for s in route.segments if s.sequence == sequence), None)
        if not segment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Segment with sequence {sequence} not found.",
            )

        await self.db.delete(segment)
        await self.db.flush()  # Ensure deletion is persisted before resequencing

        # Resequence ALL remaining segments to ensure no gaps
        # Get all segments excluding the deleted one
        segments_to_update = [s for s in route.segments if s != segment]

        # First, set all sequences to negative to avoid unique constraint violations
        for i, seg in enumerate(segments_to_update):
            seg.sequence = -(i + 1)
        await self.db.flush()

        # Now resequence from 0 to ensure consecutive ordering
        for i, seg in enumerate(segments_to_update):
            seg.sequence = i

        await self.db.flush()  # Flush to make changes available for index building

        # Rebuild route station index (part of same transaction)
        index_service = RouteIndexService(self.db)
        await index_service.build_route_station_index(route_id, auto_commit=False)

        await self.db.commit()

    async def create_schedule(
        self,
        route_id: uuid.UUID,
        user_id: uuid.UUID,
        request: CreateScheduleRequest,
    ) -> UserRouteSchedule:
        """
        Create a schedule for a route.

        Args:
            route_id: UserRoute UUID
            user_id: User UUID (for ownership check)
            request: Schedule creation request

        Returns:
            Created schedule

        Raises:
            HTTPException: 404 if route not found
        """
        # Verify ownership
        await self.get_route_by_id(route_id, user_id)

        schedule = UserRouteSchedule(
            route_id=route_id,
            days_of_week=request.days_of_week,
            start_time=request.start_time,
            end_time=request.end_time,
        )

        self.db.add(schedule)
        await self.db.commit()
        await self.db.refresh(schedule)

        return schedule

    async def update_schedule(
        self,
        route_id: uuid.UUID,
        schedule_id: uuid.UUID,
        user_id: uuid.UUID,
        request: UpdateScheduleRequest,
    ) -> UserRouteSchedule:
        """
        Update a schedule.

        Args:
            route_id: UserRoute UUID
            schedule_id: Schedule UUID
            user_id: User UUID (for ownership check)
            request: Update request

        Returns:
            Updated schedule

        Raises:
            HTTPException: 404 if route or schedule not found
        """
        # Verify route ownership
        await self.get_route_by_id(route_id, user_id)

        # Get the schedule
        result = await self.db.execute(
            select(UserRouteSchedule).where(
                UserRouteSchedule.id == schedule_id,
                UserRouteSchedule.route_id == route_id,
            )
        )
        schedule = result.scalar_one_or_none()

        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule not found.",
            )

        # Update fields
        if request.days_of_week is not None:
            schedule.days_of_week = request.days_of_week
        if request.start_time is not None:
            schedule.start_time = request.start_time
        if request.end_time is not None:
            schedule.end_time = request.end_time

        # Validate time range with None checks for defensive coding
        if (
            schedule.end_time is not None
            and schedule.start_time is not None
            and schedule.end_time <= schedule.start_time
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="end_time must be after start_time",
            )

        await self.db.commit()
        await self.db.refresh(schedule)

        return schedule

    async def delete_schedule(
        self,
        route_id: uuid.UUID,
        schedule_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """
        Delete a schedule.

        Args:
            route_id: UserRoute UUID
            schedule_id: Schedule UUID
            user_id: User UUID (for ownership check)

        Raises:
            HTTPException: 404 if route or schedule not found
        """
        # Verify route ownership
        await self.get_route_by_id(route_id, user_id)

        # Get the schedule
        result = await self.db.execute(
            select(UserRouteSchedule).where(
                UserRouteSchedule.id == schedule_id,
                UserRouteSchedule.route_id == route_id,
            )
        )
        schedule = result.scalar_one_or_none()

        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule not found.",
            )

        await self.db.delete(schedule)
        await self.db.commit()

    # ==================== Private Helper Methods ====================

    async def _validate_segments(self, segments: list[SegmentRequest]) -> None:
        """
        Validate route segments using TfL service.

        Args:
            segments: Segments to validate

        Raises:
            HTTPException: 400 if validation fails
        """
        # Convert to TfL validation format (both use TfL IDs now)
        tfl_segments = [
            RouteSegmentRequest(station_tfl_id=seg.station_tfl_id, line_tfl_id=seg.line_tfl_id) for seg in segments
        ]

        # Validate using TfL service
        valid, message, invalid_index = await self.tfl_service.validate_route(tfl_segments)

        if not valid:
            detail = f"UserRoute validation failed: {message}"
            if invalid_index is not None:
                detail += f" (segment index: {invalid_index})"

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail,
            )

    async def _validate_route_segments(self, segments: list[UserRouteSegment]) -> None:
        """
        Validate existing route segments.

        Args:
            segments: UserRoute segments to validate

        Raises:
            HTTPException: 400 if validation fails
        """
        # Convert to validation format - translate UUIDs to TfL IDs
        # Bulk fetch all stations and lines to avoid N+1 query problem
        sorted_segments = sorted(segments, key=lambda s: s.sequence)
        station_ids = {seg.station_id for seg in sorted_segments}
        line_ids = {seg.line_id for seg in sorted_segments}

        # Bulk fetch stations
        stations_result = await self.db.execute(select(Station).where(Station.id.in_(station_ids)))
        stations_map = {s.id: s for s in stations_result.scalars().all()}

        # Bulk fetch lines
        lines_result = await self.db.execute(select(Line).where(Line.id.in_(line_ids)))
        lines_map = {line.id: line for line in lines_result.scalars().all()}

        # Build segment requests using cached data
        segment_requests = []
        for seg in sorted_segments:
            station = stations_map.get(seg.station_id)
            # line_id can be None for destination segments
            line = lines_map.get(seg.line_id) if seg.line_id is not None else None

            if station is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid route segment data - station not found.",
                )

            # Line can be None for destination segments, so only check non-destination segments
            if seg.line_id is not None and line is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid route segment data - line not found.",
                )

            segment_requests.append(
                SegmentRequest(
                    sequence=seg.sequence,
                    station_tfl_id=station.tfl_id,
                    line_tfl_id=line.tfl_id if line is not None else None,
                )
            )

        await self._validate_segments(segment_requests)
