/**
 * Test Setup Configuration
 *
 * This file configures the global test environment for all Vitest tests.
 *
 * To discover existing test patterns:
 * 1. Check test-utils.tsx for helper functions (createMockAuth, createMockBackendAuth, renderWithRouter)
 * 2. Look at ProtectedRoute.test.tsx for authentication testing patterns
 * 3. Look at Routes.test.tsx for React Router testing patterns
 * 4. Look at StationCombobox.test.tsx or LineSelect.test.tsx for Radix UI component patterns
 *
 * Common patterns:
 * - Mock hooks with vi.mock() at the top of test files
 * - Use createMockAuth() and createMockBackendAuth() for auth mocking
 * - Use renderWithRouter() for components that use React Router hooks
 * - Use MemoryRouter for wrapping components that need routing context
 */

import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'

// Mock ResizeObserver for tests (used by Radix UI components)
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Mock DOM APIs for Radix UI components
// - scrollIntoView: Used by Command component (cmdk)
// - hasPointerCapture/releasePointerCapture/setPointerCapture: Used by Select component
Element.prototype.scrollIntoView = vi.fn()
Element.prototype.hasPointerCapture = vi.fn()
Element.prototype.releasePointerCapture = vi.fn()
Element.prototype.setPointerCapture = vi.fn()

// Cleanup after each test
afterEach(() => {
  cleanup()
})
