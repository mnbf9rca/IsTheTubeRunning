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
