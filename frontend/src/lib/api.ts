/**
 * API client for backend communication
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

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

let getAccessTokenFn: GetAccessTokenFn | null = null

/**
 * Set the access token getter function (called from App.tsx with Auth0)
 */
export function setAccessTokenGetter(fn: GetAccessTokenFn) {
  getAccessTokenFn = fn
}

/**
 * Fetch wrapper with error handling and JWT token injection
 */
async function fetchAPI<T>(
  endpoint: string,
  options?: RequestInit & { skipAuth?: boolean }
): Promise<T> {
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
    return null as T
  }

  return response.json()
}

/**
 * Check API health (public endpoint)
 */
export async function checkHealth(): Promise<HealthResponse> {
  return fetchAPI<HealthResponse>('/health', { skipAuth: true })
}

/**
 * Get API root information (public endpoint)
 */
export async function getRoot(): Promise<RootResponse> {
  return fetchAPI<RootResponse>('/', { skipAuth: true })
}
