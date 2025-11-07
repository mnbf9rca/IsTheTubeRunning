/**
 * API client for backend communication
 */

import { config } from './config'

const API_BASE_URL = config.api.baseUrl

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
 * User information response from /auth/me
 */
export interface UserResponse {
  id: string
  created_at: string
  updated_at: string
}

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
// Contact Management Types & API
// ============================================================================

/**
 * Email contact response
 */
export interface EmailResponse {
  id: string
  email: string
  verified: boolean
  is_primary: boolean
  created_at: string
}

/**
 * Phone contact response
 */
export interface PhoneResponse {
  id: string
  phone: string
  verified: boolean
  is_primary: boolean
  created_at: string
}

/**
 * Union type for any contact
 */
export type Contact = EmailResponse | PhoneResponse

/**
 * Response from GET /contacts endpoint
 */
export interface ContactsResponse {
  emails: EmailResponse[]
  phones: PhoneResponse[]
}

/**
 * Request to add an email
 */
export interface AddEmailRequest {
  email: string
}

/**
 * Request to add a phone
 */
export interface AddPhoneRequest {
  phone: string
}

/**
 * Request to verify a contact code
 */
export interface VerifyCodeRequest {
  contact_id: string
  code: string
}

/**
 * Response from verification code send
 */
export interface SendVerificationResponse {
  success: boolean
  message: string
}

/**
 * Response from verification code verification
 */
export interface VerifyCodeResponse {
  success: boolean
  message: string
}

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
 * Segment information (part of a route)
 */
export interface SegmentResponse {
  id: string
  sequence: number
  station_id: string
  line_id: string
}

/**
 * Schedule information (when a route is active)
 */
export interface ScheduleResponse {
  id: string
  days_of_week: string[] // ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
  start_time: string // HH:MM:SS format
  end_time: string // HH:MM:SS format
}

/**
 * Full route response with segments and schedules
 */
export interface RouteResponse {
  id: string
  name: string
  description: string | null
  active: boolean
  timezone: string
  segments: SegmentResponse[]
  schedules: ScheduleResponse[]
}

/**
 * Route list item response (summary without segments/schedules)
 */
export interface RouteListItemResponse {
  id: string
  name: string
  description: string | null
  active: boolean
  timezone: string
  segment_count: number
  schedule_count: number
}

/**
 * Request to create a new route
 */
export interface CreateRouteRequest {
  name: string
  description?: string
  active?: boolean
  timezone?: string
}

/**
 * Request to update an existing route
 */
export interface UpdateRouteRequest {
  name?: string
  description?: string
  active?: boolean
  timezone?: string
}

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
 * Request to create or update a segment
 */
export interface SegmentRequest {
  sequence: number
  station_id: string
  line_id: string
}

/**
 * Request to update a single segment
 */
export interface UpdateSegmentRequest {
  station_id?: string
  line_id?: string
}

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
 * Request to create a new schedule
 */
export interface CreateScheduleRequest {
  days_of_week: string[] // ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
  start_time: string // HH:MM:SS format
  end_time: string // HH:MM:SS format
}

/**
 * Request to update a schedule (all fields optional)
 */
export interface UpdateScheduleRequest {
  days_of_week?: string[]
  start_time?: string
  end_time?: string
}

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
// Notification Preference Types & API
// ============================================================================

/**
 * Notification method enum
 */
export type NotificationMethod = 'email' | 'sms'

/**
 * Notification preference response
 */
export interface NotificationPreferenceResponse {
  id: string
  route_id: string
  method: NotificationMethod
  target_email_id: string | null
  target_phone_id: string | null
  created_at: string
  updated_at: string
}

/**
 * Request to create a notification preference
 */
export interface CreateNotificationPreferenceRequest {
  method: NotificationMethod
  target_email_id?: string
  target_phone_id?: string
}

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
// TfL Data Types & API
// ============================================================================

/**
 * TfL line information
 */
export interface LineResponse {
  id: string
  tfl_id: string
  name: string
  color: string
  last_updated: string
}

/**
 * TfL station information
 */
export interface StationResponse {
  id: string
  tfl_id: string
  name: string
  latitude: number
  longitude: number
  lines: string[] // Array of line TfL IDs
  last_updated: string
}

/**
 * Network connection information
 */
export interface NetworkConnection {
  station_id: string
  station_tfl_id: string
  station_name: string
  line_id: string
  line_tfl_id: string
  line_name: string
}

/**
 * Network graph adjacency list
 * Maps station TfL ID to array of connected stations
 */
export type NetworkGraph = Record<string, NetworkConnection[]>

/**
 * Route validation segment request
 */
export interface RouteValidationSegment {
  station_id: string
  line_id: string
}

/**
 * Route validation response
 */
export interface RouteValidationResponse {
  valid: boolean
  message: string
  invalid_segment_index?: number
}

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
 * @param lineId Optional line ID to filter stations
 * @returns Array of stations (cached 24 hours on backend)
 * @throws {ApiError} If the request fails
 */
export async function getStations(lineId?: string): Promise<StationResponse[]> {
  const endpoint = lineId ? `/tfl/stations?line_id=${lineId}` : '/tfl/stations'
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
