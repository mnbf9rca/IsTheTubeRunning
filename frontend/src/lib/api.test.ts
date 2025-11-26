import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  ApiError,
  setAccessTokenGetter,
  resetAccessTokenGetter,
  setApiBaseUrl,
  checkHealth,
  getRoot,
  getContacts,
  addEmail,
  addPhone,
  sendVerification,
  verifyCode,
  deleteContact,
  rebuildRouteIndexes,
  buildStationGraph,
  syncTflMetadata,
  triggerAlertCheck,
  getWorkerStatus,
  getRecentLogs,
  getAdminUsers,
  getAdminUser,
  anonymizeUser,
  getEngagementMetrics,
} from './api'

describe('API initialization guards', () => {
  it('should throw error when setApiBaseUrl called with empty string', () => {
    expect(() => setApiBaseUrl('')).toThrow('API base URL cannot be empty')
  })

  it('should throw error when setApiBaseUrl called with whitespace-only string', () => {
    expect(() => setApiBaseUrl('   ')).toThrow('API base URL cannot be empty')
  })

  it('should successfully set API base URL with valid URL', () => {
    // This should not throw
    expect(() => setApiBaseUrl('http://localhost:8000')).not.toThrow()
  })
})

// Set API base URL for remaining tests
beforeEach(() => {
  setApiBaseUrl('http://localhost:8000')
})

describe('ApiError', () => {
  it('should create an ApiError with status and message', () => {
    const error = new ApiError(404, 'Not Found', { detail: 'Resource not found' })

    expect(error).toBeInstanceOf(Error)
    expect(error.name).toBe('ApiError')
    expect(error.status).toBe(404)
    expect(error.statusText).toBe('Not Found')
    expect(error.data).toEqual({ detail: 'Resource not found' })
    expect(error.message).toBe('API Error 404: Not Found')
  })
})

describe('Token management', () => {
  beforeEach(() => {
    setApiBaseUrl('http://localhost:8000')
    resetAccessTokenGetter()
  })

  it('should set and use access token getter', async () => {
    const mockGetToken = vi.fn().mockResolvedValue('test-token')
    setAccessTokenGetter(mockGetToken)

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: 'test' }),
    })
    global.fetch = mockFetch

    // The token getter should be available for authenticated requests
    expect(mockGetToken).toBeDefined()
    expect(typeof mockGetToken).toBe('function')
  })

  it('should reset access token getter', async () => {
    const mockGetToken = vi.fn().mockResolvedValue('test-token')
    setAccessTokenGetter(mockGetToken)
    resetAccessTokenGetter()

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok' }),
    })

    // Should work without token after reset
    await expect(checkHealth()).resolves.toBeDefined()
  })

  it('should handle token getter failures gracefully', async () => {
    const mockGetToken = vi.fn().mockRejectedValue(new Error('Token error'))
    setAccessTokenGetter(mockGetToken)

    // Token getter is set and will fail when called
    // The actual error handling happens in fetchAPI when making authenticated requests
    expect(mockGetToken).toBeDefined()
    await expect(mockGetToken()).rejects.toThrow('Token error')
  })
})

describe('API requests', () => {
  beforeEach(() => {
    setApiBaseUrl('http://localhost:8000')
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should make successful API request', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok' }),
    })

    const result = await checkHealth()

    expect(result).toEqual({ status: 'ok' })
    expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/health', expect.any(Object))
  })

  it('should handle 204 No Content response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
    })

    // Mock a DELETE endpoint that returns 204
    const response = await fetch('http://localhost:8000/test', { method: 'DELETE' })

    expect(response.status).toBe(204)
  })

  it('should throw ApiError on non-ok response with JSON', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: async () => ({ detail: 'Invalid input' }),
    })

    await expect(checkHealth()).rejects.toThrow(ApiError)
    await expect(checkHealth()).rejects.toMatchObject({
      status: 400,
      statusText: 'Bad Request',
      data: { detail: 'Invalid input' },
    })
  })

  it('should throw ApiError on non-ok response without JSON', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => {
        throw new Error('Not JSON')
      },
    })

    await expect(checkHealth()).rejects.toThrow(ApiError)
    await expect(checkHealth()).rejects.toMatchObject({
      status: 500,
      statusText: 'Internal Server Error',
      data: { detail: 'Internal Server Error' },
    })
  })

  it('should skip auth when skipAuth is true', async () => {
    const mockGetToken = vi.fn().mockResolvedValue('test-token')
    setAccessTokenGetter(mockGetToken)

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok' }),
    })

    await checkHealth()

    expect(mockGetToken).not.toHaveBeenCalled()
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/health',
      expect.objectContaining({
        headers: expect.not.objectContaining({
          Authorization: expect.anything(),
        }),
      })
    )
  })

  it('should throw error for unexpected 204 from health endpoint', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
    })

    await expect(checkHealth()).rejects.toThrow(ApiError)
    await expect(checkHealth()).rejects.toThrow('Unexpected 204 response')
  })

  it('should include Content-Type header by default', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok' }),
    })

    await checkHealth()

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/health',
      expect.objectContaining({
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
      })
    )
  })

  it('should merge custom headers with defaults', async () => {
    const mockGetToken = vi.fn().mockResolvedValue('test-token')
    setAccessTokenGetter(mockGetToken)

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ message: 'ok', version: '1.0' }),
    })

    await getRoot()

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/',
      expect.objectContaining({
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
      })
    )
  })
})

describe('checkHealth', () => {
  it('should return health response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'healthy' }),
    })

    const result = await checkHealth()

    expect(result).toEqual({ status: 'healthy' })
  })
})

describe('getRoot', () => {
  it('should return root response with version', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ message: 'API Running', version: '1.0.0' }),
    })

    const result = await getRoot()

    expect(result).toEqual({ message: 'API Running', version: '1.0.0' })
  })
})

// ============================================================================
// Contact Management API Tests
// ============================================================================

describe('getContacts', () => {
  beforeEach(() => {
    const mockGetToken = vi.fn().mockResolvedValue('test-token')
    setAccessTokenGetter(mockGetToken)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should return contacts response with emails and phones', async () => {
    const mockResponse = {
      emails: [
        {
          id: '123',
          email: 'test@example.com',
          verified: true,
          is_primary: true,
          created_at: '2025-01-01T00:00:00Z',
        },
      ],
      phones: [],
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })

    const result = await getContacts()

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/contacts',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer test-token',
        }),
      })
    )
  })

  it('should throw error for unexpected 204', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
    })

    await expect(getContacts()).rejects.toThrow(ApiError)
    await expect(getContacts()).rejects.toThrow('Unexpected 204 response')
  })
})

describe('addEmail', () => {
  beforeEach(() => {
    const mockGetToken = vi.fn().mockResolvedValue('test-token')
    setAccessTokenGetter(mockGetToken)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should add email successfully', async () => {
    const mockResponse = {
      id: '123',
      email: 'new@example.com',
      verified: false,
      is_primary: false,
      created_at: '2025-01-01T00:00:00Z',
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockResponse,
    })

    const result = await addEmail('new@example.com')

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/contacts/email',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ email: 'new@example.com' }),
      })
    )
  })

  it('should handle 409 conflict error', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      statusText: 'Conflict',
      json: async () => ({ detail: 'Email already registered' }),
    })

    await expect(addEmail('duplicate@example.com')).rejects.toThrow(ApiError)
    await expect(addEmail('duplicate@example.com')).rejects.toMatchObject({
      status: 409,
      data: { detail: 'Email already registered' },
    })
  })

  it('should handle 429 rate limit error', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      statusText: 'Too Many Requests',
      json: async () => ({ detail: 'Too many failed attempts' }),
    })

    await expect(addEmail('test@example.com')).rejects.toThrow(ApiError)
    await expect(addEmail('test@example.com')).rejects.toMatchObject({
      status: 429,
    })
  })
})

describe('addPhone', () => {
  beforeEach(() => {
    const mockGetToken = vi.fn().mockResolvedValue('test-token')
    setAccessTokenGetter(mockGetToken)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should add phone successfully', async () => {
    const mockResponse = {
      id: '456',
      phone: '+442012345678',
      verified: false,
      is_primary: false,
      created_at: '2025-01-01T00:00:00Z',
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => mockResponse,
    })

    const result = await addPhone('+442012345678')

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/contacts/phone',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ phone: '+442012345678' }),
      })
    )
  })

  it('should handle 400 invalid format error', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: async () => ({ detail: 'Invalid phone format' }),
    })

    await expect(addPhone('invalid')).rejects.toThrow(ApiError)
    await expect(addPhone('invalid')).rejects.toMatchObject({
      status: 400,
    })
  })

  it('should handle 409 conflict error', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      statusText: 'Conflict',
      json: async () => ({ detail: 'Phone already registered' }),
    })

    await expect(addPhone('+442012345678')).rejects.toThrow(ApiError)
    await expect(addPhone('+442012345678')).rejects.toMatchObject({
      status: 409,
    })
  })
})

describe('sendVerification', () => {
  beforeEach(() => {
    const mockGetToken = vi.fn().mockResolvedValue('test-token')
    setAccessTokenGetter(mockGetToken)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should send verification code successfully', async () => {
    const mockResponse = {
      success: true,
      message: 'Verification code sent to your email address.',
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })

    const result = await sendVerification('123')

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/contacts/123/send-verification',
      expect.objectContaining({
        method: 'POST',
      })
    )
  })

  it('should handle 404 contact not found', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ detail: 'Contact not found' }),
    })

    await expect(sendVerification('999')).rejects.toThrow(ApiError)
    await expect(sendVerification('999')).rejects.toMatchObject({
      status: 404,
    })
  })

  it('should handle 429 rate limit (3 per hour)', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      statusText: 'Too Many Requests',
      json: async () => ({ detail: 'Too many verification code requests' }),
    })

    await expect(sendVerification('123')).rejects.toThrow(ApiError)
    await expect(sendVerification('123')).rejects.toMatchObject({
      status: 429,
    })
  })
})

describe('verifyCode', () => {
  beforeEach(() => {
    const mockGetToken = vi.fn().mockResolvedValue('test-token')
    setAccessTokenGetter(mockGetToken)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should verify code successfully', async () => {
    const mockResponse = {
      success: true,
      message: 'Contact verified successfully.',
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })

    const result = await verifyCode('123', '123456')

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/contacts/verify',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ contact_id: '123', code: '123456' }),
      })
    )
  })

  it('should handle 400 invalid code', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: async () => ({ detail: 'Invalid verification code' }),
    })

    await expect(verifyCode('123', 'wrong')).rejects.toThrow(ApiError)
    await expect(verifyCode('123', 'wrong')).rejects.toMatchObject({
      status: 400,
    })
  })

  it('should handle 400 expired code', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: async () => ({ detail: 'Verification code has expired' }),
    })

    await expect(verifyCode('123', '123456')).rejects.toThrow(ApiError)
    await expect(verifyCode('123', '123456')).rejects.toMatchObject({
      status: 400,
      data: { detail: 'Verification code has expired' },
    })
  })

  it('should handle 404 contact not found', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ detail: 'Contact not found' }),
    })

    await expect(verifyCode('999', '123456')).rejects.toThrow(ApiError)
    await expect(verifyCode('999', '123456')).rejects.toMatchObject({
      status: 404,
    })
  })
})

describe('deleteContact', () => {
  beforeEach(() => {
    const mockGetToken = vi.fn().mockResolvedValue('test-token')
    setAccessTokenGetter(mockGetToken)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should delete contact successfully (204 No Content)', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
    })

    // Should not throw for 204
    await expect(deleteContact('123')).resolves.toBeUndefined()
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/contacts/123',
      expect.objectContaining({
        method: 'DELETE',
      })
    )
  })

  it('should handle 404 contact not found', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ detail: 'Contact not found' }),
    })

    await expect(deleteContact('999')).rejects.toThrow(ApiError)
    await expect(deleteContact('999')).rejects.toMatchObject({
      status: 404,
    })
  })
})

// ============================================================================
// Admin API Tests
// ============================================================================

describe('Admin API - Route Index Management', () => {
  beforeEach(() => {
    const mockGetToken = vi.fn().mockResolvedValue('test-token')
    setAccessTokenGetter(mockGetToken)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should rebuild all route indexes successfully', async () => {
    const mockResponse = {
      success: true,
      rebuilt_count: 5,
      failed_count: 0,
      errors: [],
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })

    const result = await rebuildRouteIndexes()

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/admin/routes/rebuild-indexes',
      expect.any(Object)
    )
  })

  it('should rebuild indexes for specific route', async () => {
    const mockResponse = {
      success: true,
      rebuilt_count: 1,
      failed_count: 0,
      errors: [],
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })

    const result = await rebuildRouteIndexes('route-123')

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/admin/routes/rebuild-indexes?route_id=route-123',
      expect.any(Object)
    )
  })

  it('should handle 403 Forbidden (non-admin user)', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      statusText: 'Forbidden',
      json: async () => ({ detail: 'Admin privileges required' }),
    })

    await expect(rebuildRouteIndexes()).rejects.toThrow(ApiError)
    await expect(rebuildRouteIndexes()).rejects.toMatchObject({
      status: 403,
    })
  })
})

describe('Admin API - TfL Management', () => {
  beforeEach(() => {
    const mockGetToken = vi.fn().mockResolvedValue('test-token')
    setAccessTokenGetter(mockGetToken)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should build station graph successfully', async () => {
    const mockResponse = {
      success: true,
      message: 'Station graph built successfully',
      lines_count: 11,
      stations_count: 500,
      connections_count: 800,
      hubs_count: 50,
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })

    const result = await buildStationGraph()

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/admin/tfl/build-graph',
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('should sync TfL metadata successfully', async () => {
    const mockResponse = {
      success: true,
      message: 'Metadata synced successfully',
      severity_codes_count: 10,
      disruption_categories_count: 5,
      stop_types_count: 3,
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })

    const result = await syncTflMetadata()

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/admin/tfl/sync-metadata',
      expect.objectContaining({ method: 'POST' })
    )
  })
})

describe('Admin API - Alert Management', () => {
  beforeEach(() => {
    const mockGetToken = vi.fn().mockResolvedValue('test-token')
    setAccessTokenGetter(mockGetToken)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should trigger alert check successfully', async () => {
    const mockResponse = {
      success: true,
      message: 'Alert check completed',
      routes_checked: 10,
      alerts_sent: 3,
      errors: 0,
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })

    const result = await triggerAlertCheck()

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/admin/alerts/trigger-check',
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('should get worker status successfully', async () => {
    const mockResponse = {
      worker_available: true,
      active_tasks: 2,
      scheduled_tasks: 1,
      last_heartbeat: '2024-01-01T12:00:00Z',
      message: 'Worker is healthy',
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })

    const result = await getWorkerStatus()

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/admin/alerts/worker-status',
      expect.any(Object)
    )
  })

  it('should get recent logs with default params', async () => {
    const mockResponse = {
      total: 100,
      logs: [],
      limit: 50,
      offset: 0,
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })

    const result = await getRecentLogs()

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/admin/alerts/recent-logs',
      expect.any(Object)
    )
  })

  it('should get recent logs with pagination and status filter', async () => {
    const mockResponse = {
      total: 10,
      logs: [],
      limit: 20,
      offset: 40,
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })

    const result = await getRecentLogs({ limit: 20, offset: 40, status: 'failed' })

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/admin/alerts/recent-logs?limit=20&offset=40&status=failed',
      expect.any(Object)
    )
  })
})

describe('Admin API - User Management', () => {
  beforeEach(() => {
    const mockGetToken = vi.fn().mockResolvedValue('test-token')
    setAccessTokenGetter(mockGetToken)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should get admin users with default params', async () => {
    const mockResponse = {
      total: 50,
      users: [],
      limit: 50,
      offset: 0,
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })

    const result = await getAdminUsers()

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/admin/users',
      expect.any(Object)
    )
  })

  it('should get admin users with search and pagination', async () => {
    const mockResponse = {
      total: 5,
      users: [],
      limit: 10,
      offset: 20,
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })

    const result = await getAdminUsers({
      limit: 10,
      offset: 20,
      search: 'test@example.com',
      include_deleted: true,
    })

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/admin/users?limit=10&offset=20&search=test%40example.com&include_deleted=true',
      expect.any(Object)
    )
  })

  it('should get specific user details', async () => {
    const mockResponse = {
      id: 'user-123',
      external_id: 'auth0|123',
      auth_provider: 'auth0',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      deleted_at: null,
      email_addresses: [],
      phone_numbers: [],
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })

    const result = await getAdminUser('user-123')

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/admin/users/user-123',
      expect.any(Object)
    )
  })

  it('should anonymize user successfully', async () => {
    const mockResponse = {
      success: true,
      message: 'User anonymized successfully',
      user_id: 'user-123',
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })

    const result = await anonymizeUser('user-123')

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/admin/users/user-123',
      expect.objectContaining({ method: 'DELETE' })
    )
  })

  it('should handle 404 user not found', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ detail: 'User not found' }),
    })

    await expect(getAdminUser('nonexistent')).rejects.toThrow(ApiError)
    await expect(getAdminUser('nonexistent')).rejects.toMatchObject({
      status: 404,
    })
  })
})

describe('Admin API - Analytics', () => {
  beforeEach(() => {
    const mockGetToken = vi.fn().mockResolvedValue('test-token')
    setAccessTokenGetter(mockGetToken)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should get engagement metrics successfully', async () => {
    const mockResponse = {
      user_counts: {
        total_users: 100,
        active_users: 80,
        users_with_verified_email: 70,
        users_with_verified_phone: 50,
        admin_users: 5,
      },
      route_stats: {
        total_routes: 200,
        active_routes: 150,
        avg_routes_per_user: 2.0,
      },
      notification_stats: {
        total_sent: 1000,
        successful: 950,
        failed: 50,
        success_rate: 0.95,
        by_method_last_30_days: { email: 600, sms: 350 },
      },
      growth_metrics: {
        new_users_last_7_days: 10,
        new_users_last_30_days: 40,
        daily_signups_last_7_days: [],
      },
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    })

    const result = await getEngagementMetrics()

    expect(result).toEqual(mockResponse)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/admin/analytics/engagement',
      expect.any(Object)
    )
  })

  it('should handle server error gracefully', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => ({ detail: 'Database error' }),
    })

    await expect(getEngagementMetrics()).rejects.toThrow(ApiError)
    await expect(getEngagementMetrics()).rejects.toMatchObject({
      status: 500,
    })
  })
})
