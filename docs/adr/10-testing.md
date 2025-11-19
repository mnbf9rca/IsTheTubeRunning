# Testing Strategy

## Comprehensive Test Coverage Philosophy

### Status
Active

### Context
Hobby projects often skimp on testing to move faster, leading to regressions and frustration when making changes. While this is a hobby project, maintaining quality and preventing regressions is important for long-term sustainability and learning.

### Decision
Despite being a hobby project, we prioritize good, comprehensive tests covering both happy paths and exception paths. Test coverage should be maintained above 95% for backend code. All critical user flows must have integration tests. Tests are not optional - they prevent regressions and make refactoring safer.

### Consequences
**Easier:**
- Safe refactoring (tests catch regressions immediately)
- Confidence when making changes (know if something breaks)
- Documentation through tests (tests show how code should be used)
- Faster debugging (failing test points to exact problem)
- Learning best practices (writing good tests improves code design)
- Long-term maintainability (can come back after months and change code safely)

**More Difficult:**
- More upfront development time (write test for every feature)
- Need to maintain tests alongside code (tests can become stale)
- Learning curve for testing patterns (mocking, fixtures, async testing)
- Sometimes need to refactor code to make it testable

---

## Test Database Setup

### Status
Active

### Context
Each test needs isolated database to prevent test pollution. Manually creating databases or setting `DATABASE_URL` is error-prone and requires coordination.

### Decision
`pytest-postgresql` automatically creates isolated test databases for each test with Alembic migrations. DO NOT manually create test databases or set `DATABASE_URL` in pytest commands - the test infrastructure handles this automatically via the `db_session` fixture in `conftest.py`.

### Consequences
**Easier:**
- Automatic test database creation (no manual setup)
- Isolated tests (no shared state between tests)
- Migrations run automatically (database schema matches application)
- Fast test execution (each test uses fresh database)

**More Difficult:**
- Must use `db_session` fixture correctly
- Cannot connect to test database manually (it's ephemeral)
- Debugging database state requires print statements or breakpoints

---

## Test Authentication Pattern

### Status
Active

### Context
Testing authenticated endpoints requires generating JWT tokens that match test users. Mismatched `external_id` between user and token causes 403 errors.

### Decision
When testing authenticated endpoints, use `test_user` + `auth_headers_for_user` fixtures together. The `auth_headers_for_user` fixture generates a JWT token that matches the `test_user`'s `external_id`, ensuring test data and authenticated requests use the same user. DO NOT use `test_user` + `auth_headers` together as they create different users with mismatched `external_id`s.

### Consequences
**Easier:**
- Correct fixture pairing ensures tests pass
- Clear pattern to follow (`test_user` + `auth_headers_for_user`)
- Matches production behavior (token `external_id` matches user)

**More Difficult:**
- Must remember correct fixture pairing (documentation helps)
- Two separate fixtures (`auth_headers` vs `auth_headers_for_user`) can be confusing

---

## NullPool for Async Test Isolation

### Status
Active

### Context
Async SQLAlchemy tests with pytest-asyncio fail with "Task attached to a different loop" errors when using standard connection pooling. This occurs because pytest-asyncio creates new event loops per test, but pooled connections are tied to the original loop.

### Decision
Use `sqlalchemy.pool.NullPool` for database connections in test environments (`app/core/database.py` when `DEBUG=true`, `tests/conftest.py` for test fixtures). Each database operation creates a fresh connection instead of pooling.

### Consequences
**Easier:**
- No event loop errors in async tests
- Standard solution for async SQLAlchemy testing
- Simple configuration change (pool_class=NullPool)

**More Difficult:**
- Slightly slower tests (no connection reuse)
- Must remember to use NullPool in tests (but configured automatically)

---

## Async Test Mocking Strategy

### Status
Active (Updated: Issue #200, pydantic-tfl-api v3.0.0)

### Context
Testing TfL service requires mocking async client methods from pydantic-tfl-api v3. With native async clients, we can use standard async mocking patterns.

### Decision
Mock async client methods directly using `patch.object()` with `AsyncMock`. Pattern: `with patch.object(tfl_service.line_client, "MethodName", new_callable=AsyncMock, return_value=mock_response):`. For multiple responses, use `side_effect=mock_responses`.

### Consequences
**Easier:**
- Standard Python async mocking (intuitive for developers)
- Clear what's being mocked (specific client method)
- Avoids indirect mocking of event loop internals
- Test helper functions accept `client_attr` and `client_method` parameters for flexibility

**More Difficult:**
- Slightly more verbose for multiple client mocks (need multiple `patch.object` contexts)

---

## Test Database Dependency Override Pattern

### Status
Active

### Context
Integration tests using `AsyncClient` with `ASGITransport(app=app)` need to use test database instead of production database URL from settings. Without override, tests fail with "relation does not exist" errors.

### Decision
When creating fixtures that use `AsyncClient` with `ASGITransport(app=app)`, MUST override `app.dependency_overrides[get_db]` to use the test `db_session` fixture. Pattern: Import `get_db` from `app.core.database`, create override function `async def override_get_db() -> AsyncGenerator[AsyncSession]: yield db_session`, set `app.dependency_overrides[get_db] = override_get_db`, use try/finally to clear overrides.

### Consequences
**Easier:**
- Tests use correct database (test database with migrations)
- Clear error messages when override is missing
- Standard pattern for FastAPI testing

**More Difficult:**
- Must remember to add dependency override in fixtures
- Boilerplate code in each fixture
- Easy to forget try/finally cleanup

---

## IntegrityError Recovery Test Pattern

### Status
Active

### Context
Testing error recovery code (catching `IntegrityError`, rolling back, continuing with queries) requires REAL database commits. Standard `db_session` fixture uses SAVEPOINT transactions, which don't accurately test recovery because: (1) sync listener conflicts with async rollback, (2) rollback would erase all test data.

### Decision
Use `fresh_db_session` fixture which creates a new database per test with Alembic migrations. This is slower (~2s vs ~0.1s) but supports testing real-world error recovery code paths. Currently used by 5 tests: race condition handling in user creation, duplicate email/phone detection with different casing/formatting. The `fresh_async_client` fixture pairs with `fresh_db_session` for API testing.

### Consequences
**Easier:**
- Can test REAL error recovery (IntegrityError handling)
- Matches production behavior exactly
- No sync/async conflicts with rollback

**More Difficult:**
- Much slower tests (~2s per test vs ~0.1s)
- Should only be used when necessary (not for all tests)
- Need separate fixture (`fresh_db_session` vs `db_session`)

---

## Admin User Creation CLI Tool

### Status
Active

### Context
Testing admin-only functionality requires creating admin users. Manually running SQL commands is error-prone and doesn't follow DRY principles. Test fixtures contain reusable logic that should be available outside tests.

### Decision
Created CLI tool (`uv run python -m app.cli`) for admin user management with shared utility functions in `backend/app/utils/admin_helpers.py`. Primary command is `create-admin` which creates an admin user in one step. The `admin_user` fixture uses these shared helpers to maintain DRY principles.

### Consequences
**Easier:**
- Create admin users with single CLI command (no SQL required)
- Shared logic between CLI and test fixtures (DRY)
- Frontend developers can create admin users for testing
- Type-safe with comprehensive error handling

**More Difficult:**
- Must remember to use CLI tool instead of manual SQL
- CLI requires running from backend directory with `uv run`
