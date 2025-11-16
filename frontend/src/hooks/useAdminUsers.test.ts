import { renderHook, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useAdminUsers } from './useAdminUsers'
import { ApiError } from '../lib/api'
import type { PaginatedUsersResponse, UserDetailResponse, AnonymiseUserResponse } from '../lib/api'

// Mock the API module
vi.mock('../lib/api', async () => {
  const actual = await vi.importActual('../lib/api')
  return {
    ...actual,
    getAdminUsers: vi.fn(),
    getAdminUser: vi.fn(),
    anonymizeUser: vi.fn(),
  }
})

// Import mocked functions
import * as api from '../lib/api'

describe('useAdminUsers', () => {
  const mockPaginatedResponse: PaginatedUsersResponse = {
    total: 100,
    users: [
      {
        id: 'user-1',
        external_id: 'auth0|123',
        auth_provider: 'auth0',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-01T00:00:00Z',
        deleted_at: null,
        email_addresses: [
          {
            id: 'email-1',
            email: 'user1@example.com',
            verified: true,
            is_primary: true,
          },
        ],
        phone_numbers: [],
      },
      {
        id: 'user-2',
        external_id: 'auth0|456',
        auth_provider: 'auth0',
        created_at: '2025-01-02T00:00:00Z',
        updated_at: '2025-01-02T00:00:00Z',
        deleted_at: '2025-01-10T00:00:00Z',
        email_addresses: [],
        phone_numbers: [
          {
            id: 'phone-1',
            phone: '+442012345678',
            verified: false,
            is_primary: false,
          },
        ],
      },
    ],
    limit: 50,
    offset: 0,
  }

  const mockUserDetail: UserDetailResponse = {
    id: 'user-1',
    external_id: 'auth0|123',
    auth_provider: 'auth0',
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    deleted_at: null,
    email_addresses: [
      {
        id: 'email-1',
        email: 'user1@example.com',
        verified: true,
        is_primary: true,
      },
    ],
    phone_numbers: [],
  }

  const mockAnonymizeResponse: AnonymiseUserResponse = {
    success: true,
    message: 'User anonymized successfully',
    user_id: 'user-1',
  }

  beforeEach(() => {
    vi.clearAllMocks()
    // Default mock implementation
    vi.mocked(api.getAdminUsers).mockResolvedValue(mockPaginatedResponse)
    vi.mocked(api.getAdminUser).mockResolvedValue(mockUserDetail)
    vi.mocked(api.anonymizeUser).mockResolvedValue(mockAnonymizeResponse)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('initialization', () => {
    it('should fetch users on mount', async () => {
      const { result } = renderHook(() => useAdminUsers())

      // Initially loading
      expect(result.current.loading).toBe(true)
      expect(result.current.users).toBeNull()

      // Wait for fetch to complete
      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.users).toEqual(mockPaginatedResponse)
      expect(result.current.error).toBeNull()
      expect(api.getAdminUsers).toHaveBeenCalledTimes(1)
      expect(api.getAdminUsers).toHaveBeenCalledWith({
        limit: 50,
        offset: 0,
        search: undefined,
        include_deleted: undefined,
      })
    })

    it('should handle fetch error on mount', async () => {
      const mockError = new ApiError(500, 'Internal Server Error')
      vi.mocked(api.getAdminUsers).mockRejectedValue(mockError)

      const { result } = renderHook(() => useAdminUsers())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.error).toEqual(mockError)
      expect(result.current.users).toBeNull()
    })

    it('should initialize with correct default state', async () => {
      const { result } = renderHook(() => useAdminUsers())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.currentPage).toBe(1)
      expect(result.current.pageSize).toBe(50)
      expect(result.current.searchQuery).toBe('')
      expect(result.current.includeDeleted).toBe(false)
    })
  })

  describe('pagination', () => {
    it('should calculate total pages correctly', async () => {
      const { result } = renderHook(() => useAdminUsers())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.totalUsers).toBe(100)
      expect(result.current.totalPages).toBe(2) // 100 users / 50 per page = 2 pages
    })

    it('should handle page change and fetch new data', async () => {
      const { result } = renderHook(() => useAdminUsers())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Change to page 2
      act(() => {
        result.current.setPage(2)
      })

      await waitFor(() => {
        expect(api.getAdminUsers).toHaveBeenCalledWith({
          limit: 50,
          offset: 50, // page 2 offset
          search: undefined,
          include_deleted: undefined,
        })
      })

      expect(result.current.currentPage).toBe(2)
    })

    it('should change page size and reset to page 1', async () => {
      const { result } = renderHook(() => useAdminUsers())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Change to page 2 first
      act(() => {
        result.current.setPage(2)
      })

      await waitFor(() => {
        expect(result.current.currentPage).toBe(2)
      })

      // Change page size
      act(() => {
        result.current.setPageSize(100)
      })

      await waitFor(() => {
        expect(result.current.currentPage).toBe(1) // Reset to page 1
        expect(result.current.pageSize).toBe(100)
      })

      await waitFor(() => {
        expect(api.getAdminUsers).toHaveBeenCalledWith({
          limit: 100,
          offset: 0,
          search: undefined,
          include_deleted: undefined,
        })
      })
    })

    it('should handle total pages calculation with no users', async () => {
      vi.mocked(api.getAdminUsers).mockResolvedValue({
        total: 0,
        users: [],
        limit: 50,
        offset: 0,
      })

      const { result } = renderHook(() => useAdminUsers())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.totalPages).toBe(0) // 0 pages when no users
    })
  })

  describe('search functionality', () => {
    it('should handle search query and reset to page 1', async () => {
      const { result } = renderHook(() => useAdminUsers())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Change to page 2 first
      act(() => {
        result.current.setPage(2)
      })

      await waitFor(() => {
        expect(result.current.currentPage).toBe(2)
      })

      // Set search query
      act(() => {
        result.current.setSearchQuery('user@example.com')
      })

      await waitFor(() => {
        expect(result.current.currentPage).toBe(1) // Reset to page 1
        expect(result.current.searchQuery).toBe('user@example.com')
      })

      await waitFor(() => {
        expect(api.getAdminUsers).toHaveBeenCalledWith({
          limit: 50,
          offset: 0,
          search: 'user@example.com',
          include_deleted: undefined,
        })
      })
    })

    it('should handle empty search query', async () => {
      const { result } = renderHook(() => useAdminUsers())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      act(() => {
        result.current.setSearchQuery('')
      })

      await waitFor(() => {
        expect(api.getAdminUsers).toHaveBeenCalledWith({
          limit: 50,
          offset: 0,
          search: undefined, // Empty string becomes undefined
          include_deleted: undefined,
        })
      })
    })
  })

  describe('filter functionality', () => {
    it('should handle include deleted filter and reset to page 1', async () => {
      const { result } = renderHook(() => useAdminUsers())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Change to page 2 first
      act(() => {
        result.current.setPage(2)
      })

      await waitFor(() => {
        expect(result.current.currentPage).toBe(2)
      })

      // Enable include deleted
      act(() => {
        result.current.setIncludeDeleted(true)
      })

      await waitFor(() => {
        expect(result.current.currentPage).toBe(1) // Reset to page 1
        expect(result.current.includeDeleted).toBe(true)
      })

      await waitFor(() => {
        expect(api.getAdminUsers).toHaveBeenCalledWith({
          limit: 50,
          offset: 0,
          search: undefined,
          include_deleted: true,
        })
      })
    })

    it('should handle disabling include deleted filter', async () => {
      const { result } = renderHook(() => useAdminUsers())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Enable include deleted
      act(() => {
        result.current.setIncludeDeleted(true)
      })

      await waitFor(() => {
        expect(result.current.includeDeleted).toBe(true)
      })

      // Disable include deleted
      act(() => {
        result.current.setIncludeDeleted(false)
      })

      await waitFor(() => {
        expect(result.current.includeDeleted).toBe(false)
      })

      await waitFor(() => {
        expect(api.getAdminUsers).toHaveBeenCalledWith({
          limit: 50,
          offset: 0,
          search: undefined,
          include_deleted: undefined, // false becomes undefined
        })
      })
    })
  })

  describe('user details', () => {
    it('should fetch user details', async () => {
      const { result } = renderHook(() => useAdminUsers())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      let details: UserDetailResponse | undefined

      await act(async () => {
        details = await result.current.getUserDetails('user-1')
      })

      expect(details).toEqual(mockUserDetail)
      expect(api.getAdminUser).toHaveBeenCalledWith('user-1')
    })

    it('should handle user details fetch error', async () => {
      const mockError = new ApiError(404, 'User not found')
      vi.mocked(api.getAdminUser).mockRejectedValue(mockError)

      const { result } = renderHook(() => useAdminUsers())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      await act(async () => {
        await expect(result.current.getUserDetails('nonexistent')).rejects.toThrow()
      })
    })
  })

  describe('user anonymization', () => {
    it('should anonymize user and refresh list', async () => {
      const { result } = renderHook(() => useAdminUsers())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      const initialCallCount = vi.mocked(api.getAdminUsers).mock.calls.length

      let response: AnonymiseUserResponse | undefined

      await act(async () => {
        response = await result.current.anonymizeUser('user-1')
      })

      expect(response).toEqual(mockAnonymizeResponse)
      expect(api.anonymizeUser).toHaveBeenCalledWith('user-1')

      // Should refresh list after anonymization
      await waitFor(() => {
        expect(api.getAdminUsers).toHaveBeenCalledTimes(initialCallCount + 1)
      })
    })

    it('should handle anonymization error', async () => {
      const mockError = new ApiError(403, 'Forbidden')
      vi.mocked(api.anonymizeUser).mockRejectedValue(mockError)

      const { result } = renderHook(() => useAdminUsers())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      await act(async () => {
        await expect(result.current.anonymizeUser('user-1')).rejects.toThrow()
      })

      // Wait for error state to be set
      await waitFor(() => {
        expect(result.current.error).toEqual(mockError)
      })
    })
  })

  describe('refresh functionality', () => {
    it('should refresh users with current filters', async () => {
      const { result } = renderHook(() => useAdminUsers())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Set some filters
      act(() => {
        result.current.setSearchQuery('test')
        result.current.setIncludeDeleted(true)
        result.current.setPage(2)
      })

      await waitFor(() => {
        expect(result.current.searchQuery).toBe('test')
      })

      const callCountBefore = vi.mocked(api.getAdminUsers).mock.calls.length

      // Refresh
      await act(async () => {
        await result.current.refresh()
      })

      expect(api.getAdminUsers).toHaveBeenCalledTimes(callCountBefore + 1)
      expect(api.getAdminUsers).toHaveBeenCalledWith({
        limit: 50,
        offset: 50, // page 2
        search: 'test',
        include_deleted: true,
      })
    })
  })

  describe('combined filters and pagination', () => {
    it('should handle multiple filters with pagination', async () => {
      const { result } = renderHook(() => useAdminUsers())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Apply multiple filters
      act(() => {
        result.current.setSearchQuery('admin')
        result.current.setIncludeDeleted(true)
        result.current.setPageSize(25)
        result.current.setPage(3)
      })

      await waitFor(() => {
        expect(result.current.searchQuery).toBe('admin')
        expect(result.current.includeDeleted).toBe(true)
        expect(result.current.pageSize).toBe(25)
        expect(result.current.currentPage).toBe(3)
      })

      await waitFor(() => {
        expect(api.getAdminUsers).toHaveBeenCalledWith({
          limit: 25,
          offset: 50, // page 3 with 25 per page = (3-1) * 25
          search: 'admin',
          include_deleted: true,
        })
      })
    })
  })
})
