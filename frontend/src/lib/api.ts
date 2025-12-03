/**
 * API client for backend communication
 *
 * ⚠️  IMPORTANT: Do NOT import types from this module!
 * All types should be imported from '@/types' instead.
 *
 * Although TypeScript allows importing types from this module (because they
 * appear in function signatures), the convention is to import from @/types
 * for consistency and to maintain a single source of truth for type definitions.
 *
 * ❌ BAD:  import type { DisruptionResponse } from '@/lib/api'
 * ✅ GOOD: import type { DisruptionResponse } from '@/types'
 */

import type {
  UserResponse,
  ContactsResponse,
  EmailResponse,
  PhoneResponse,
  AddEmailRequest,
  AddPhoneRequest,
  SendVerificationResponse,
  VerifyCodeRequest,
  VerifyCodeResponse,
  RouteListItemResponse,
  RouteResponse,
  CreateRouteRequest,
  UpdateRouteRequest,
  SegmentResponse,
  SegmentRequest,
  UpdateSegmentRequest,
  CreateScheduleRequest,
  ScheduleResponse,
  UpdateScheduleRequest,
  NotificationPreferenceResponse,
  CreateNotificationPreferenceRequest,
  LineResponse,
  StationResponse,
  NetworkGraph,
  RouteValidationSegment,
  RouteValidationResponse,
  RebuildIndexesResponse,
  BuildGraphResponse,
  SyncMetadataResponse,
  TriggerCheckResponse,
  WorkerStatusResponse,
  NotificationStatus,
  RecentLogsResponse,
  PaginatedUsersResponse,
  UserDetailResponse,
  AnonymiseUserResponse,
  EngagementMetrics,
  RouteDisruptionResponse,
  StationDisruptionResponse,
  GroupedLineDisruptionResponse,
} from '@/types'

/**
 * Module-level API base URL
 * Set via setApiBaseUrl() after config loads
 */
let API_BASE_URL: string | null = null

/**
 * Set the API base URL from runtime configuration
 *
 * Called by ConfigLoader after config is fetched and validated.
 * Must be called before making any API requests.
 *
 * @param baseUrl The API base URL from configuration
 * @throws {Error} If baseUrl is empty or invalid
 */
export function setApiBaseUrl(baseUrl: string): void {
  if (!baseUrl || baseUrl.trim() === '') {
    throw new Error('API base URL cannot be empty')
  }
  API_BASE_URL = baseUrl
}

export interface HealthResponse {
  status: string
}

export interface RootResponse {
  message: string
  version: string
}

export class ApiError extends Error {
  status: number
  statusText: string
  data?: unknown

  constructor(status: number, statusText: string, data?: unknown) {
    super(`API Error ${status}: ${statusText}`)
    this.name = 'ApiError'
    this.status = status
    this.statusText = statusText
    this.data = data
  }
}

type GetAccessTokenFn = () => Promise<string>

/**
 * Global reference to the access token getter function.
 *
 * This is set by the App component when Auth0 context is initialized,
 * and reset on unmount to prevent stale references. The function is called
 * on each API request that requires authentication.
 *
 * LIFECYCLE:
 * - Set when App component mounts and Auth0 is initialized
 * - Updated if getAccessToken reference changes (e.g., after re-authentication)
 * - Reset to null (or rejection function) on App unmount
 */
let getAccessTokenFn: GetAccessTokenFn | null = null

/**
 * Set the access token getter function
 *
 * This should be called from the App component with Auth0's getAccessToken function.
 * The provided function will be called on each authenticated API request.
 *
 * @param fn Function that returns a promise resolving to an access token
 *
 * @example
 * // In App.tsx
 * const { getAccessToken } = useAuth()
 * useEffect(() => {
 *   setAccessTokenGetter(getAccessToken)
 *   return () => setAccessTokenGetter(() => Promise.reject(new Error('Unmounted')))
 * }, [getAccessToken])
 */
export function setAccessTokenGetter(fn: GetAccessTokenFn) {
  getAccessTokenFn = fn
}

/**
 * Reset the access token getter (useful for logout or cleanup)
 *
 * @example
 * // On logout
 * resetAccessTokenGetter()
 */
export function resetAccessTokenGetter() {
  getAccessTokenFn = null
}

/**
 * Fetch wrapper with error handling and JWT token injection
 *
 * Makes an API request and returns the parsed JSON response. For endpoints that
 * return 204 No Content (typically DELETE operations), this function returns `null`.
 *
 * @template T The expected response type
 * @param endpoint The API endpoint path (e.g., '/health')
 * @param options Fetch options with optional skipAuth flag
 * @returns Promise resolving to the parsed response data, or null for 204 responses
 * @throws {ApiError} If the response status is not ok (non-2xx)
 *
 * @example
 * // Endpoint returning data
 * const data = await fetchAPI<HealthResponse>('/health')
 * console.log(data.status) // OK
 *
 * @example
 * // Endpoint returning 204 No Content (e.g., DELETE)
 * const result = await fetchAPI<void>('/users/123', { method: 'DELETE' })
 * if (result === null) {
 *   console.log('Delete successful')
 * }
 */
async function fetchAPI<T>(
  endpoint: string,
  options?: RequestInit & { skipAuth?: boolean }
): Promise<T | null> {
  // Guard: Ensure API base URL is configured before making requests
  if (!API_BASE_URL) {
    throw new Error(
      'API base URL not configured. ConfigLoader must complete before making API requests.'
    )
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  // Merge existing headers if provided
  if (options?.headers) {
    const existingHeaders = new Headers(options.headers)
    existingHeaders.forEach((value, key) => {
      headers[key] = value
    })
  }

  // Add Authorization header if getAccessToken is available and skipAuth is not true
  if (getAccessTokenFn && !options?.skipAuth) {
    try {
      const token = await getAccessTokenFn()
      headers['Authorization'] = `Bearer ${token}`
    } catch (error) {
      console.error('Failed to get access token:', error)
      // Continue without token - server will return 401 if required
    }
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  })

  // Handle different error responses
  if (!response.ok) {
    let errorData
    try {
      errorData = await response.json()
    } catch {
      // Response is not JSON
      errorData = { detail: response.statusText }
    }

    throw new ApiError(response.status, response.statusText, errorData)
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return null
  }

  return response.json()
}

/**
 * Check API health (public endpoint)
 *
 * @returns Health status response
 * @throws {ApiError} If the health check fails
 */
export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetchAPI<HealthResponse>('/health', { skipAuth: true })
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from health endpoint')
  }
  return response
}

/**
 * Get API root information (public endpoint)
 *
 * @returns API root information with version
 * @throws {ApiError} If the request fails
 */
export async function getRoot(): Promise<RootResponse> {
  const response = await fetchAPI<RootResponse>('/', { skipAuth: true })
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from root endpoint')
  }
  return response
}

// ============================================================================
// Authentication Types & API
// ============================================================================

/**
 * Get current authenticated user information
 *
 * This endpoint validates the JWT token with the backend and returns user info.
 * It also automatically creates a new user record on first authenticated request.
 *
 * @returns Current user information
 * @throws {ApiError} 401 if token is invalid or expired
 */
export async function getCurrentUser(): Promise<UserResponse> {
  const response = await fetchAPI<UserResponse>('/auth/me')
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from auth/me endpoint')
  }
  return response
}

// ============================================================================
// Contact Management API
// ============================================================================

/**
 * Get all contacts for the authenticated user
 *
 * @returns ContactsResponse with emails and phones arrays
 * @throws {ApiError} If the request fails
 */
export async function getContacts(): Promise<ContactsResponse> {
  const response = await fetchAPI<ContactsResponse>('/contacts')
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from contacts endpoint')
  }
  return response
}

/**
 * Add a new email address
 *
 * @param email The email address to add
 * @returns The created email contact
 * @throws {ApiError} 409 if email already exists, 429 if rate limited
 */
export async function addEmail(email: string): Promise<EmailResponse> {
  const response = await fetchAPI<EmailResponse>('/contacts/email', {
    method: 'POST',
    body: JSON.stringify({ email } as AddEmailRequest),
  })
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from add email endpoint')
  }
  return response
}

/**
 * Add a new phone number
 *
 * @param phone The phone number to add (E.164 format)
 * @returns The created phone contact
 * @throws {ApiError} 400 if invalid format, 409 if phone already exists, 429 if rate limited
 */
export async function addPhone(phone: string): Promise<PhoneResponse> {
  const response = await fetchAPI<PhoneResponse>('/contacts/phone', {
    method: 'POST',
    body: JSON.stringify({ phone } as AddPhoneRequest),
  })
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from add phone endpoint')
  }
  return response
}

/**
 * Send verification code to a contact
 *
 * @param contactId The contact ID to verify
 * @returns Response confirming code was sent
 * @throws {ApiError} 404 if contact not found, 429 if rate limited (3 per hour)
 */
export async function sendVerification(contactId: string): Promise<SendVerificationResponse> {
  const response = await fetchAPI<SendVerificationResponse>(
    `/contacts/${contactId}/send-verification`,
    { method: 'POST' }
  )
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from send verification endpoint')
  }
  return response
}

/**
 * Verify a contact with the provided code
 *
 * @param contactId The contact ID to verify
 * @param code The 6-digit verification code
 * @returns Response confirming verification success
 * @throws {ApiError} 400 if code invalid/expired, 404 if contact not found
 */
export async function verifyCode(contactId: string, code: string): Promise<VerifyCodeResponse> {
  const response = await fetchAPI<VerifyCodeResponse>('/contacts/verify', {
    method: 'POST',
    body: JSON.stringify({ contact_id: contactId, code } as VerifyCodeRequest),
  })
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from verify code endpoint')
  }
  return response
}

/**
 * Delete a contact
 *
 * @param contactId The contact ID to delete
 * @throws {ApiError} 404 if contact not found
 */
export async function deleteContact(contactId: string): Promise<void> {
  await fetchAPI<void>(`/contacts/${contactId}`, { method: 'DELETE' })
}

// ============================================================================
// Route Management Types & API
// ============================================================================

/**
 * Get all routes for the authenticated user
 *
 * @returns Array of route summaries
 * @throws {ApiError} If the request fails
 */
export async function getRoutes(): Promise<RouteListItemResponse[]> {
  const response = await fetchAPI<RouteListItemResponse[]>('/routes')
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from routes endpoint')
  }
  return response
}

/**
 * Get a single route with full details
 *
 * @param routeId The route ID to fetch
 * @returns Full route details including segments and schedules
 * @throws {ApiError} 404 if route not found
 */
export async function getRoute(routeId: string): Promise<RouteResponse> {
  const response = await fetchAPI<RouteResponse>(`/routes/${routeId}`)
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from route endpoint')
  }
  return response
}

/**
 * Create a new route
 *
 * @param data Route creation data
 * @returns The created route
 * @throws {ApiError} 400 if validation fails
 */
export async function createRoute(data: CreateRouteRequest): Promise<RouteResponse> {
  const response = await fetchAPI<RouteResponse>('/routes', {
    method: 'POST',
    body: JSON.stringify(data),
  })
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from create route endpoint')
  }
  return response
}

/**
 * Update an existing route
 *
 * @param routeId The route ID to update
 * @param data Route update data (partial updates supported)
 * @returns The updated route
 * @throws {ApiError} 404 if route not found, 400 if validation fails
 */
export async function updateRoute(
  routeId: string,
  data: UpdateRouteRequest
): Promise<RouteResponse> {
  const response = await fetchAPI<RouteResponse>(`/routes/${routeId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from update route endpoint')
  }
  return response
}

/**
 * Delete a route
 *
 * @param routeId The route ID to delete
 * @throws {ApiError} 404 if route not found
 */
export async function deleteRoute(routeId: string): Promise<void> {
  await fetchAPI<void>(`/routes/${routeId}`, { method: 'DELETE' })
}

// ============================================================================
// Segment Management Types & API
// ============================================================================

/**
 * Replace all segments for a route (batch upsert)
 *
 * @param routeId The route ID to update
 * @param segments Array of segments (min 2 required, consecutive sequences starting from 0)
 * @returns The updated list of segments
 * @throws {ApiError} 400 if validation fails (min 2 segments, invalid sequences)
 */
export async function upsertSegments(
  routeId: string,
  segments: SegmentRequest[]
): Promise<SegmentResponse[]> {
  const response = await fetchAPI<SegmentResponse[]>(`/routes/${routeId}/segments`, {
    method: 'PUT',
    body: JSON.stringify({ segments }),
  })
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from upsert segments endpoint')
  }
  return response
}

/**
 * Update a single segment
 *
 * @param routeId The route ID
 * @param sequence The sequence number of the segment to update
 * @param data Partial segment data to update
 * @returns The updated segment
 * @throws {ApiError} 404 if route or segment not found, 400 if validation fails
 */
export async function updateSegment(
  routeId: string,
  sequence: number,
  data: UpdateSegmentRequest
): Promise<SegmentResponse> {
  const response = await fetchAPI<SegmentResponse>(`/routes/${routeId}/segments/${sequence}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from update segment endpoint')
  }
  return response
}

/**
 * Delete a segment
 *
 * Deletes the segment and resequences remaining segments automatically.
 * Cannot delete if fewer than 2 segments would remain.
 *
 * @param routeId The route ID
 * @param sequence The sequence number of the segment to delete
 * @throws {ApiError} 404 if route or segment not found, 400 if <2 segments would remain
 */
export async function deleteSegment(routeId: string, sequence: number): Promise<void> {
  await fetchAPI<void>(`/routes/${routeId}/segments/${sequence}`, { method: 'DELETE' })
}

// ============================================================================
// Schedule Management Types & API
// ============================================================================

/**
 * Create a new schedule for a route
 *
 * @param routeId The route ID
 * @param data Schedule creation data
 * @returns The created schedule
 * @throws {ApiError} 400 if validation fails (invalid days, end_time <= start_time)
 */
export async function createSchedule(
  routeId: string,
  data: CreateScheduleRequest
): Promise<ScheduleResponse> {
  const response = await fetchAPI<ScheduleResponse>(`/routes/${routeId}/schedules`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from create schedule endpoint')
  }
  return response
}

/**
 * Update an existing schedule
 *
 * @param routeId The route ID
 * @param scheduleId The schedule ID to update
 * @param data Partial schedule data to update
 * @returns The updated schedule
 * @throws {ApiError} 404 if route or schedule not found, 400 if validation fails
 */
export async function updateSchedule(
  routeId: string,
  scheduleId: string,
  data: UpdateScheduleRequest
): Promise<ScheduleResponse> {
  const response = await fetchAPI<ScheduleResponse>(`/routes/${routeId}/schedules/${scheduleId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from update schedule endpoint')
  }
  return response
}

/**
 * Delete a schedule
 *
 * @param routeId The route ID
 * @param scheduleId The schedule ID to delete
 * @throws {ApiError} 404 if route or schedule not found
 */
export async function deleteSchedule(routeId: string, scheduleId: string): Promise<void> {
  await fetchAPI<void>(`/routes/${routeId}/schedules/${scheduleId}`, { method: 'DELETE' })
}

// ============================================================================
// Notification Preference API
// ============================================================================

/**
 * Get all notification preferences for a route
 *
 * @param routeId The route ID
 * @returns Array of notification preferences
 * @throws {ApiError} 404 if route not found
 */
export async function getNotificationPreferences(
  routeId: string
): Promise<NotificationPreferenceResponse[]> {
  const response = await fetchAPI<NotificationPreferenceResponse[]>(
    `/routes/${routeId}/notifications`
  )
  if (response === null) {
    throw new ApiError(204, 'Unexpected 204 response from get notification preferences endpoint')
  }
  return response
}

/**
 * Create a new notification preference for a route
 *
 * @param routeId The route ID
 * @param data The notification preference data
 * @returns The created notification preference
 * @throws {ApiError} 400 if invalid data, 404 if route/contact not found, 409 if duplicate
 */
export async function createNotificationPreference(
  routeId: string,
  data: CreateNotificationPreferenceRequest
): Promise<NotificationPreferenceResponse> {
  const response = await fetchAPI<NotificationPreferenceResponse>(
    `/routes/${routeId}/notifications`,
    {
      method: 'POST',
      body: JSON.stringify(data),
    }
  )
  if (response === null) {
    throw new ApiError(204, 'Unexpected 204 response from create notification preference endpoint')
  }
  return response
}

/**
 * Delete a notification preference
 *
 * @param routeId The route ID
 * @param preferenceId The notification preference ID
 * @throws {ApiError} 404 if preference not found
 */
export async function deleteNotificationPreference(
  routeId: string,
  preferenceId: string
): Promise<void> {
  await fetchAPI<void>(`/routes/${routeId}/notifications/${preferenceId}`, { method: 'DELETE' })
}

// ============================================================================
// TfL Data API
// ============================================================================

/**
 * Get all TfL tube lines
 *
 * @returns Array of lines (cached 24 hours on backend)
 * @throws {ApiError} If the request fails
 */
export async function getLines(): Promise<LineResponse[]> {
  const response = await fetchAPI<LineResponse[]>('/tfl/lines')
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from lines endpoint')
  }
  return response
}

/**
 * Get all TfL stations, optionally filtered by line
 *
 * Stations are deduplicated by hub - hubs like "Seven Sisters" appear once
 * with aggregated lines from all child stations (e.g., Overground + Victoria).
 *
 * @param lineId Optional line ID to filter stations
 * @returns Array of hub-grouped stations (cached 24 hours on backend)
 * @throws {ApiError} If the request fails
 */
export async function getStations(lineId?: string): Promise<StationResponse[]> {
  const params = new URLSearchParams()
  if (lineId) {
    params.append('line_id', lineId)
  }
  // Request deduplicated stations to group hubs into single entries
  params.append('deduplicated', 'true')

  const endpoint = `/tfl/stations?${params.toString()}`
  const response = await fetchAPI<StationResponse[]>(endpoint)
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from stations endpoint')
  }
  return response
}

/**
 * Get the station connection network graph
 *
 * Returns an adjacency list mapping each station to its connected stations.
 * Used for constraining route building to valid connections.
 *
 * @returns Network graph adjacency list
 * @throws {ApiError} If the request fails or graph not built yet
 */
export async function getNetworkGraph(): Promise<NetworkGraph> {
  const response = await fetchAPI<NetworkGraph>('/tfl/network-graph')
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from network-graph endpoint')
  }
  return response
}

/**
 * Validate a route's segment sequence
 *
 * Checks if the segments form a valid path through the network graph.
 *
 * @param segments Array of segments to validate (min 2)
 * @returns Validation result with error details if invalid
 * @throws {ApiError} If the request fails
 */
export async function validateRoute(
  segments: RouteValidationSegment[]
): Promise<RouteValidationResponse> {
  const response = await fetchAPI<RouteValidationResponse>('/tfl/validate-route', {
    method: 'POST',
    body: JSON.stringify({ segments }),
  })
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from validate-route endpoint')
  }
  return response
}

/**
 * Get all TfL line disruptions (grouped by line)
 *
 * Returns current disruptions affecting tube, DLR, Overground, and Elizabeth line.
 * Data is grouped by line, with all statuses for each line combined and sorted by severity.
 * Data is cached on backend based on TfL API cache headers.
 *
 * @returns Array of grouped line disruptions (one entry per line with multiple statuses)
 * @throws {ApiError} If the request fails
 */
export async function getDisruptions(): Promise<GroupedLineDisruptionResponse[]> {
  const response = await fetchAPI<GroupedLineDisruptionResponse[]>('/tfl/disruptions')
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from disruptions endpoint')
  }
  return response
}

/**
 * Get disruptions affecting the authenticated user's routes
 *
 * Returns only disruptions that affect the user's configured routes,
 * with route-specific context (affected segments and stations).
 *
 * @param activeOnly Filter to only active routes (default: true)
 * @returns Array of route-specific disruptions
 * @throws {ApiError} 503 if TfL API unavailable, 401 if not authenticated
 */
export async function getRouteDisruptions(
  activeOnly: boolean = true
): Promise<RouteDisruptionResponse[]> {
  const params = new URLSearchParams()
  params.append('active_only', activeOnly.toString())

  const response = await fetchAPI<RouteDisruptionResponse[]>(
    `/routes/disruptions?${params.toString()}`
  )
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from route disruptions endpoint')
  }
  return response
}

/**
 * Get all TfL station-level disruptions
 *
 * Returns current station-specific disruptions (closures, lift outages, etc.)
 * as opposed to line-wide disruptions.
 *
 * @returns Array of station disruptions
 * @throws {ApiError} If the request fails
 */
export async function getStationDisruptions(): Promise<StationDisruptionResponse[]> {
  const response = await fetchAPI<StationDisruptionResponse[]>('/tfl/station-disruptions')
  if (!response) {
    throw new ApiError(204, 'Unexpected 204 response from station disruptions endpoint')
  }
  return response
}

// ============================================================================
// Admin API Types & Functions
// ============================================================================

// ----------------------------------------------------------------------------
// Admin Route Index Management
// ----------------------------------------------------------------------------

// ----------------------------------------------------------------------------
// Admin TfL Metadata Management
// ----------------------------------------------------------------------------

// ----------------------------------------------------------------------------
// Admin Alert Management
// ----------------------------------------------------------------------------

// ----------------------------------------------------------------------------
// Admin User Management
// ----------------------------------------------------------------------------

// ----------------------------------------------------------------------------
// Admin Analytics
// ----------------------------------------------------------------------------

// ----------------------------------------------------------------------------
// Admin API Functions
// ----------------------------------------------------------------------------

/**
 * Helper to assert that a response is not null (204 No Content)
 *
 * Admin endpoints should always return data. A 204 response is unexpected
 * and indicates a misconfiguration or server error.
 *
 * @template T The expected response type
 * @param response The response from fetchAPI
 * @param endpointName Name of the endpoint for error message
 * @returns The response if not null
 * @throws {ApiError} If response is null (204)
 */
function assertResponse<T>(response: T | null, endpointName: string): T {
  if (!response) {
    throw new ApiError(204, `Unexpected 204 response from ${endpointName} endpoint`)
  }
  return response
}

/**
 * Rebuild route alert indexes for efficient alert matching
 *
 * @param routeId Optional route ID to rebuild indexes for a specific route
 * @returns Result with counts of rebuilt/failed indexes
 * @throws {ApiError} 403 if not admin, or other server errors
 */
export async function rebuildRouteIndexes(routeId?: string): Promise<RebuildIndexesResponse> {
  const searchParams = new URLSearchParams()
  if (routeId) searchParams.append('route_id', routeId)

  const endpoint = `/admin/routes/rebuild-indexes${
    searchParams.toString() ? `?${searchParams.toString()}` : ''
  }`
  const response = await fetchAPI<RebuildIndexesResponse>(endpoint, {
    method: 'POST',
  })
  return assertResponse(response, 'rebuild-indexes')
}

/**
 * Build the TfL station connection graph
 *
 * Fetches all TfL lines and their stations, then builds the connection graph
 * used for route validation.
 *
 * @returns Result with counts of lines, stations, connections, and hubs
 * @throws {ApiError} 403 if not admin, or other server errors
 */
export async function buildStationGraph(): Promise<BuildGraphResponse> {
  const response = await fetchAPI<BuildGraphResponse>('/admin/tfl/build-graph', {
    method: 'POST',
  })
  return assertResponse(response, 'build-graph')
}

/**
 * Sync TfL metadata (severity codes, disruption categories, stop types)
 *
 * @returns Result with counts of synced metadata items
 * @throws {ApiError} 403 if not admin, or other server errors
 */
export async function syncTflMetadata(): Promise<SyncMetadataResponse> {
  const response = await fetchAPI<SyncMetadataResponse>('/admin/tfl/sync-metadata', {
    method: 'POST',
  })
  return assertResponse(response, 'sync-metadata')
}

/**
 * Manually trigger an alert check for all active routes
 *
 * @returns Result with counts of routes checked and alerts sent
 * @throws {ApiError} 403 if not admin, or other server errors
 */
export async function triggerAlertCheck(): Promise<TriggerCheckResponse> {
  const response = await fetchAPI<TriggerCheckResponse>('/admin/alerts/trigger-check', {
    method: 'POST',
  })
  return assertResponse(response, 'trigger-check')
}

/**
 * Get Celery worker status
 *
 * @returns Worker availability, task counts, and last heartbeat
 * @throws {ApiError} 403 if not admin, or other server errors
 */
export async function getWorkerStatus(): Promise<WorkerStatusResponse> {
  const response = await fetchAPI<WorkerStatusResponse>('/admin/alerts/worker-status')
  return assertResponse(response, 'worker-status')
}

export interface RecentLogsParams {
  limit?: number
  offset?: number
  status?: NotificationStatus
}

/**
 * Get recent notification logs with pagination and optional status filter
 *
 * @param params Pagination and filter parameters
 * @returns Paginated list of notification logs
 * @throws {ApiError} 403 if not admin, or other server errors
 */
export async function getRecentLogs(params?: RecentLogsParams): Promise<RecentLogsResponse> {
  const searchParams = new URLSearchParams()
  if (params?.limit) searchParams.append('limit', params.limit.toString())
  if (params?.offset) searchParams.append('offset', params.offset.toString())
  if (params?.status) searchParams.append('status', params.status)

  const endpoint = `/admin/alerts/recent-logs${
    searchParams.toString() ? `?${searchParams.toString()}` : ''
  }`
  const response = await fetchAPI<RecentLogsResponse>(endpoint)
  return assertResponse(response, 'recent-logs')
}

export interface AdminUsersParams {
  limit?: number
  offset?: number
  search?: string
  include_deleted?: boolean
}

/**
 * Get paginated list of all users (admin only)
 *
 * @param params Pagination and filter parameters
 * @returns Paginated list of users with contact info
 * @throws {ApiError} 403 if not admin, or other server errors
 */
export async function getAdminUsers(params?: AdminUsersParams): Promise<PaginatedUsersResponse> {
  const searchParams = new URLSearchParams()
  if (params?.limit) searchParams.append('limit', params.limit.toString())
  if (params?.offset) searchParams.append('offset', params.offset.toString())
  if (params?.search) searchParams.append('search', params.search)
  if (params?.include_deleted) searchParams.append('include_deleted', 'true')

  const endpoint = `/admin/users${searchParams.toString() ? `?${searchParams.toString()}` : ''}`
  const response = await fetchAPI<PaginatedUsersResponse>(endpoint)
  return assertResponse(response, 'admin users')
}

/**
 * Get detailed information for a specific user (admin only)
 *
 * @param userId User ID to fetch details for
 * @returns User details with contact information
 * @throws {ApiError} 403 if not admin, 404 if user not found, or other server errors
 */
export async function getAdminUser(userId: string): Promise<UserDetailResponse> {
  const response = await fetchAPI<UserDetailResponse>(`/admin/users/${userId}`)
  return assertResponse(response, 'admin user')
}

/**
 * Anonymize a user (privacy-focused deletion)
 *
 * Removes all PII (emails, phones, verification codes), anonymizes external_id,
 * and deactivates routes. Preserves analytics data.
 *
 * @param userId User ID to anonymize
 * @returns Result with success status and message
 * @throws {ApiError} 403 if not admin, 404 if user not found, or other server errors
 */
export async function anonymizeUser(userId: string): Promise<AnonymiseUserResponse> {
  const response = await fetchAPI<AnonymiseUserResponse>(`/admin/users/${userId}`, {
    method: 'DELETE',
  })
  return assertResponse(response, 'anonymize user')
}

/**
 * Get engagement metrics and analytics (admin only)
 *
 * Returns comprehensive metrics including user counts, route stats,
 * notification stats, and growth metrics.
 *
 * @returns Engagement metrics
 * @throws {ApiError} 403 if not admin, or other server errors
 */
export async function getEngagementMetrics(): Promise<EngagementMetrics> {
  const response = await fetchAPI<EngagementMetrics>('/admin/analytics/engagement')
  return assertResponse(response, 'engagement metrics')
}
