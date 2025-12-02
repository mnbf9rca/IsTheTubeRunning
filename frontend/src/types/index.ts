/**
 * API Type Definitions
 *
 * This file provides convenient type aliases for the auto-generated OpenAPI types.
 * Types are generated from the backend OpenAPI specification using openapi-typescript.
 *
 * Usage:
 *   import type { UserResponse, LineResponse } from '@/types'
 *
 * To regenerate types after backend schema changes:
 *   cd backend && uv run python scripts/generate_openapi.py
 *   cd frontend && npm run generate-types
 */

// Re-export base types from generated file
export type { components, paths, operations } from './api-generated'

import type { components } from './api-generated'

// Type aliases for all API response/request schemas
// These provide backward compatibility with the original manual type definitions

// Note: HealthResponse and RootResponse are simple inline types, not schemas
// They remain defined in api.ts

// Authentication
export type UserResponse = components['schemas']['UserResponse']

// Contacts
export type EmailResponse = components['schemas']['EmailResponse']
export type PhoneResponse = components['schemas']['PhoneResponse']
export type Contact = EmailResponse | PhoneResponse
export type ContactsResponse = components['schemas']['ContactsResponse']
export type AddEmailRequest = components['schemas']['AddEmailRequest']
export type AddPhoneRequest = components['schemas']['AddPhoneRequest']
export type VerifyCodeRequest = components['schemas']['VerifyCodeRequest']
export type SendVerificationResponse = components['schemas']['SendVerificationResponse']
export type VerifyCodeResponse = components['schemas']['VerifyCodeResponse']
export type EmailAddressItem = components['schemas']['EmailAddressItem']
export type PhoneNumberItem = components['schemas']['PhoneNumberItem']

// Routes
export type SegmentResponse = components['schemas']['UserRouteSegmentResponse']
export type ScheduleResponse = components['schemas']['UserRouteScheduleResponse']
export type RouteResponse = components['schemas']['UserRouteResponse']
export type RouteListItemResponse = components['schemas']['UserRouteListItemResponse']
export type CreateRouteRequest = components['schemas']['CreateUserRouteRequest']
export type UpdateRouteRequest = components['schemas']['UpdateUserRouteRequest']
export type SegmentRequest = components['schemas']['UserRouteSegmentRequest']
export type UpdateSegmentRequest = components['schemas']['UpdateUserRouteSegmentRequest']
export type CreateScheduleRequest = components['schemas']['CreateUserRouteScheduleRequest']
export type UpdateScheduleRequest = components['schemas']['UpdateUserRouteScheduleRequest']

// Notification preferences
export type NotificationMethod = components['schemas']['NotificationMethod']
export type NotificationPreferenceResponse = components['schemas']['NotificationPreferenceResponse']
export type CreateNotificationPreferenceRequest =
  components['schemas']['CreateNotificationPreferenceRequest']

// TfL data
export type RouteVariant = components['schemas']['RouteVariant']
export type LineResponse = components['schemas']['LineResponse']
export type StationResponse = components['schemas']['StationResponse']
export type NetworkConnection = components['schemas']['NetworkConnection']
export type NetworkGraph = Record<string, NetworkConnection[]>
export type RouteValidationSegment = components['schemas']['RouteSegmentRequest']
export type RouteValidationResponse = components['schemas']['RouteValidationResponse']

// Admin - route indexes
export type RebuildIndexesResponse = components['schemas']['RebuildIndexesResponse']

// Admin - TfL metadata
export type SyncMetadataResponse = components['schemas']['SyncMetadataResponse']
export type BuildGraphResponse = components['schemas']['BuildGraphResponse']

// Admin - alerts
export type TriggerCheckResponse = components['schemas']['TriggerCheckResponse']
export type WorkerStatusResponse = components['schemas']['WorkerStatusResponse']
export type NotificationStatus = components['schemas']['NotificationStatus']
export type NotificationLogItem = components['schemas']['NotificationLogItem']
export type RecentLogsResponse = components['schemas']['RecentLogsResponse']
// Note: RecentLogsParams is a frontend-only query parameter helper, defined in api.ts

// Admin - users
export type UserListItem = components['schemas']['UserListItem']
export type PaginatedUsersResponse = components['schemas']['PaginatedUsersResponse']
export type UserDetailResponse = components['schemas']['UserDetailResponse']
export type AnonymiseUserResponse = components['schemas']['AnonymiseUserResponse']
// Note: AdminUsersParams is a frontend-only query parameter helper, defined in api.ts

// Admin - analytics
export type UserCountMetrics = components['schemas']['UserCountMetrics']
export type RouteStatMetrics = components['schemas']['RouteStatMetrics']
export type NotificationStatMetrics = components['schemas']['NotificationStatMetrics']
export type DailySignup = components['schemas']['DailySignup']
export type GrowthMetrics = components['schemas']['GrowthMetrics']
export type EngagementMetrics = components['schemas']['EngagementMetrics']
