# Testing Issues & Action Plan

**Branch**: `feature/phase-10-pr2.5-fix-auth-flow`
**Date**: 2025-11-06
**Status**: Partially complete - 16/19 tests passing, 2 critical issues remaining

---

## Summary

Unit tests have been updated to support the new authentication flow, but two critical issues remain:

1. **ProtectedRoute.test.tsx** hangs indefinitely, blocking the test suite
2. **Callback error scenarios** (401/500/network) are not unit tested

---

## ✅ Current Status

### Passing Tests (16/16)

**Login.test.tsx** (3/3 passing ✅)
- ✅ Redirects to intended route after Auth0 authentication
- ✅ Redirects to dashboard by default when no intended route
- ✅ Shows loading state while Auth0 is loading

**Header.test.tsx** (7/7 passing ✅)
- ✅ Shows login button when not authenticated
- ✅ Calls login when login button clicked
- ✅ Does not show navigation when not authenticated
- ✅ Shows loading skeleton while authenticating
- ✅ Shows navigation when authenticated
- ✅ Renders avatar button with user initials
- ✅ Calls handleLogout when logout clicked

**Callback.test.tsx** (6/6 passing ✅)
- ✅ Shows loading spinner while Auth0 is loading
- ✅ Redirects to dashboard when already backend authenticated
- ✅ Shows error when Auth0 authentication fails
- ✅ Does not redirect while still loading
- ✅ Redirects to login when not authenticated with Auth0
- ✅ Shows verifying state when validating with backend

### Run Command
```bash
cd frontend
npm test -- --run src/pages/Login.test.tsx src/components/layout/Header.test.tsx src/pages/Callback.test.tsx
```

---

## ❌ Issue #1: ProtectedRoute.test.tsx Hangs Indefinitely

### Problem
Running `ProtectedRoute.test.tsx` causes vitest to hang indefinitely, never completing. This blocks the entire test suite when run together.

### Symptoms
```bash
# This command hangs forever:
npm test -- --run src/components/ProtectedRoute.test.tsx

# Output shows "RUN" but never progresses
```

### Root Cause (Suspected)
The `ProtectedRoute` component uses `<Navigate>` from `react-router-dom`, which may be triggering infinite navigation loops in the test environment when mocked incorrectly.

**Component behavior**:
- Calls `useLocation()` to get current location
- Calls `<Navigate>` with `state={{ from: location.pathname }}`
- This may create a render loop in tests

### Current Test Code
**File**: `frontend/src/components/ProtectedRoute.test.tsx`

```typescript
describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render children when authenticated', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: true,
      isValidating: false,
      user: { id: '1', created_at: '2024-01-01', updated_at: '2024-01-01' },
      error: null,
    })

    render(
      <BrowserRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </BrowserRouter>
    )

    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('should show loading state when loading', () => {
    // ... similar pattern
  })

  it('should redirect to login when not authenticated', () => {
    // THIS TEST LIKELY HANGS
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      isValidating: false,
      user: null,
      error: null,
    })

    render(
      <BrowserRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </BrowserRouter>
    )

    // Never gets here - component redirects infinitely
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })
})
```

### Proposed Solutions

**Option A: Use MemoryRouter with Routes**
```typescript
import { MemoryRouter, Routes, Route } from 'react-router-dom'

it('should redirect to login when not authenticated', async () => {
  mockUseAuth.mockReturnValue({
    isAuthenticated: false,
    isLoading: false,
  })
  mockUseBackendAuth.mockReturnValue({
    isBackendAuthenticated: false,
    isValidating: false,
    user: null,
    error: null,
  })

  render(
    <MemoryRouter initialEntries={['/protected']}>
      <Routes>
        <Route path="/login" element={<div>Login Page</div>} />
        <Route path="/protected" element={
          <ProtectedRoute>
            <div>Protected Content</div>
          </ProtectedRoute>
        } />
      </Routes>
    </MemoryRouter>
  )

  await waitFor(() => {
    expect(screen.getByText('Login Page')).toBeInTheDocument()
  })
})
```

**Option B: Mock navigate and verify it was called**
```typescript
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

it('should call navigate to login when not authenticated', () => {
  // ... setup mocks

  render(
    <BrowserRouter>
      <ProtectedRoute>
        <div>Protected Content</div>
      </ProtectedRoute>
    </BrowserRouter>
  )

  expect(mockNavigate).toHaveBeenCalledWith('/login', expect.anything())
})
```

**Option C: Skip these tests temporarily**
```typescript
describe.skip('ProtectedRoute', () => {
  // Tests commented out until navigation mocking is fixed
})
```

### Recommended Action
**Try Option A first** (MemoryRouter with Routes) - this is the most realistic test setup and should prevent navigation loops.

---

## ❌ Issue #2: Missing Callback Error Scenario Tests

### Problem
The `Callback` component handles critical error scenarios (401, 403, 500, network errors) that are **NOT currently unit tested**. These scenarios need comprehensive test coverage.

### Why Current Tests Don't Cover These

The current tests mock the contexts (`useAuth`, `useBackendAuth`) at the hook level, but the error handling happens **inside the component's useEffect** when `validateWithBackend()` is called.

**The issue**: Mocking `validateWithBackend` to reject doesn't cause the component's internal state (`validationState`, `errorMessage`) to update because:
1. Component has its own internal state machine
2. State updates happen in try/catch inside useEffect
3. Tests can't observe these internal state transitions with current mocking approach

### Missing Test Scenarios

From `frontend/src/pages/Callback.tsx`, these error states need testing:

#### 1. **Backend 401/403 Error** → `auth_denied` state
**Expected behavior**:
- Shows: "Authentication denied by server. Logging out..."
- Calls `forceLogout()` after 2 second delay
- No retry button

#### 2. **Backend 500+ Error** → `server_error` state
**Expected behavior**:
- Shows: "Server error (500). Please try again."
- Shows "Retry" button
- Shows "Back to Login" button

#### 3. **Network Error** → `server_error` state
**Expected behavior**:
- Shows: "Unable to connect to server. Please check your connection."
- Shows "Retry" button
- Shows "Back to Login" button

### Current Code Structure

```typescript
// frontend/src/pages/Callback.tsx (relevant excerpt)
export default function Callback() {
  const { isAuthenticated, isLoading, error: authError } = useAuth()
  const { isBackendAuthenticated, validateWithBackend, forceLogout } = useBackendAuth()
  const navigate = useNavigate()
  const [validationState, setValidationState] = useState<
    'idle' | 'validating' | 'success' | 'auth_denied' | 'server_error'
  >('idle')
  const [errorMessage, setErrorMessage] = useState<string>('')

  useEffect(() => {
    // ... complex validation logic
    try {
      await validateWithBackend()
      // Success path
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 401 || error.status === 403) {
          setValidationState('auth_denied')
          setErrorMessage('Authentication denied by server. Logging out...')
          setTimeout(() => forceLogout(), 2000)
        } else if (error.status >= 500) {
          setValidationState('server_error')
          setErrorMessage(`Server error (${error.status}). Please try again.`)
        }
      } else {
        setValidationState('server_error')
        setErrorMessage('Unable to connect to server. Please check your connection.')
      }
    }
  }, [/* deps */])

  // Render logic based on validationState
  if (validationState === 'auth_denied') {
    return <Alert>/* ... */</Alert>
  }
  if (validationState === 'server_error') {
    return <Alert>/* ... with retry buttons */</Alert>
  }
  // ...
}
```

### Why Testing Is Difficult

**Problem**: The component's error handling is triggered by:
1. Component calls `validateWithBackend()` in useEffect
2. `validateWithBackend()` throws error
3. Component catches error and updates internal state
4. Component re-renders with error UI

**But when we mock** `validateWithBackend`:
```typescript
mockValidateWithBackend.mockRejectedValueOnce(new ApiError(401, 'Unauthorized'))
```

The component **never calls the real validation logic**, so internal state never updates.

### Proposed Solutions

#### Option 1: Test the UI States Directly (Integration Test Approach)

Instead of testing the error flow, test that the component renders correctly **when already in an error state**. This requires refactoring the component.

**Refactor**: Extract error state management to BackendAuthContext
- Move `validationState` and `errorMessage` to `BackendAuthContext`
- Component becomes a presentation layer
- Tests can mock the context to be in error states

**Example**:
```typescript
// After refactoring BackendAuthContext to expose error state
it('should show auth denied message when backend returns 401', () => {
  mockUseAuth.mockReturnValue({
    isAuthenticated: true,
    isLoading: false,
  })
  mockUseBackendAuth.mockReturnValue({
    isBackendAuthenticated: false,
    validationState: 'auth_denied', // ← New: context exposes this
    errorMessage: 'Authentication denied by server. Logging out...',
    validateWithBackend: mockValidateWithBackend,
    forceLogout: mockForceLogout,
  })

  render(<BrowserRouter><Callback /></BrowserRouter>)

  expect(screen.getByText('Authentication denied by server. Logging out...')).toBeInTheDocument()
})
```

#### Option 2: Use Integration Tests with MSW (Mock Service Worker)

Install MSW to mock at the API level instead of context level:

```bash
npm install --save-dev msw
```

**Example test**:
```typescript
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'

const server = setupServer(
  http.post('/api/v1/auth/validate', () => {
    return HttpResponse.json(
      { error: 'Unauthorized' },
      { status: 401 }
    )
  })
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

it('should handle 401 error from backend', async () => {
  render(<BackendAuthProvider><Callback /></BackendAuthProvider>)

  await waitFor(() => {
    expect(screen.getByText('Authentication denied by server. Logging out...')).toBeInTheDocument()
  })
})
```

#### Option 3: Extract Validation Logic to Testable Function

Extract the error handling logic from useEffect into a pure function that can be tested in isolation:

```typescript
// New file: frontend/src/lib/validateBackend.ts
export async function handleBackendValidation(
  validateWithBackend: () => Promise<void>,
  callbacks: {
    onAuthDenied: (message: string) => void
    onServerError: (message: string) => void
    onSuccess: () => void
  }
) {
  try {
    await validateWithBackend()
    callbacks.onSuccess()
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 401 || error.status === 403) {
        callbacks.onAuthDenied('Authentication denied by server. Logging out...')
      } else if (error.status >= 500) {
        callbacks.onServerError(`Server error (${error.status}). Please try again.`)
      }
    } else {
      callbacks.onServerError('Unable to connect to server. Please check your connection.')
    }
  }
}

// Unit test the function directly
describe('handleBackendValidation', () => {
  it('calls onAuthDenied for 401 errors', async () => {
    const mockValidate = vi.fn().mockRejectedValueOnce(new ApiError(401, 'Unauthorized'))
    const onAuthDenied = vi.fn()

    await handleBackendValidation(mockValidate, {
      onAuthDenied,
      onServerError: vi.fn(),
      onSuccess: vi.fn(),
    })

    expect(onAuthDenied).toHaveBeenCalledWith('Authentication denied by server. Logging out...')
  })
})
```

### Recommended Action

**Recommended**: **Option 1** (Refactor to expose error state in context)

**Reasoning**:
1. Makes component more testable
2. Improves separation of concerns (logic in context, presentation in component)
3. Doesn't change functionality (user explicitly said refactoring for testability is fine)
4. No new dependencies needed
5. Tests remain fast unit tests

**Implementation steps**:
1. Update `BackendAuthContext` to track validation state and error messages
2. Update `Callback` component to read state from context instead of managing it internally
3. Write tests that mock context in various error states
4. Verify all error scenarios are covered

---

## Action Plan

### Immediate (High Priority)

1. **Fix ProtectedRoute.test.tsx** (blocking test suite)
   - Try Option A (MemoryRouter with Routes)
   - If that fails, try Option B (mock navigate)
   - Last resort: Skip tests temporarily

2. **Add Callback error scenario tests**
   - Refactor `BackendAuthContext` to expose `validationState` and `errorMessage`
   - Refactor `Callback` component to use context state
   - Write 3 new tests for 401/500/network errors
   - Verify tests pass

### Testing Commands

```bash
# Run just the passing tests
cd frontend
npm test -- --run src/pages/Login.test.tsx src/components/layout/Header.test.tsx src/pages/Callback.test.tsx

# Try running ProtectedRoute after fixes
npm test -- --run src/components/ProtectedRoute.test.tsx

# Run all tests after both issues fixed
npm test -- --run

# Lint check
npm run lint:fix
```

### Success Criteria

- ✅ All test files complete without hanging
- ✅ At least 19 tests passing (16 current + 3 new error scenarios)
- ✅ No ESLint errors
- ✅ Tests finish in < 5 seconds

---

## Files to Modify

### For ProtectedRoute Fix
- `frontend/src/components/ProtectedRoute.test.tsx` - Fix navigation mocking

### For Callback Error Tests
- `frontend/src/contexts/BackendAuthContext.tsx` - Add validation state/error exposure
- `frontend/src/pages/Callback.tsx` - Refactor to use context state
- `frontend/src/pages/Callback.test.tsx` - Add 3 new error scenario tests

---

## References

### Relevant Documentation
- React Testing Library: https://testing-library.com/docs/react-testing-library/intro/
- React Router Testing: https://reactrouter.com/en/main/start/testing
- Vitest Mocking: https://vitest.dev/guide/mocking.html

### Related Files
- `frontend/src/hooks/useAuth.ts` - Auth0 authentication hook
- `frontend/src/contexts/BackendAuthContext.tsx` - Backend validation context
- `frontend/src/lib/api.ts` - API client and ApiError class
- `frontend/src/components/ProtectedRoute.tsx` - Protected route component
- `frontend/src/pages/Callback.tsx` - OAuth callback handler

### Test Results Document
- `TEST_RESULTS_PR2.5.md` - Comprehensive test results for this PR

---

## Notes

- User preference: Refactoring code for testability is acceptable as long as functionality doesn't change
- No Playwright/E2E tests wanted - all testing should be unit tests
- Backend tests (10/10) are already passing
- Manual browser testing via Playwright MCP was used to verify flows work end-to-end
