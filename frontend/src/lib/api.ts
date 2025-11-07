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
