# Architecture Decision Records (ADR)

This document captures key architectural decisions made during the development of the TfL Disruption Alert System.

Note: when running commands in /backend ALWAYS use `uv run` never naked `python`. Do not use pip.

---

## Key Architectural Decisions Made

1. **Monorepo**: Easier management for hobby project, shared types
2. **Auth0**: Offload auth complexity, focus on core features
3. **Multi-line routes**: More realistic commute scenarios
4. **Celery + Redis**: Proper async job handling for scalability
5. **Azure VM + Docker Compose**: Full control, cost-effective within free credits, no per-service pricing
6. **Cloudflare + UFW**: Free WAF, SSL, CDN; restrict access to Cloudflare IPs only
7. **SOPS/age + Docker secrets**: Self-contained secret management, no external service dependency
8. **shadcn/ui**: Lightweight, customizable, modern Tailwind-based components
9. **Code-based verification**: Consistent UX for email and SMS
10. **uv for Python**: Fast, modern package management
11. **Tailwind CSS v4**: Using latest v4 (not v3). Configuration and syntax differ significantly from v3. Use Context7 or WebFetch tools to get current v4 documentation when needed.
12. **UUIDs for Primary Keys**: Prevents enumeration attacks, better security for user data (Phase 2)
13. **Soft Deletes**: Audit trail and data recovery capability via deleted_at timestamp (Phase 2)
14. **JSON for Route Schedules**: PostgreSQL JSON support for days_of_week arrays (Phase 2)
15. **Required Config**: DATABASE_URL, REDIS_URL, ALLOWED_ORIGINS must be provided; no misleading defaults (Phase 2)
16. **DB Credential Separation**: App runs with limited DB permissions; migrations in separate CI/init container with admin access (Phase 2)
17. **python-dotenv-vault for Secrets**: Replaced SOPS/age with python-dotenv-vault for simpler encrypted secret management; locally managed (no cloud service), pre-commit hooks auto-rebuild .env.vault (Phase 2)
18. **Rate Limiting Strategy**: Two-tier rate limiting for security - verification codes (3/hour to prevent spam) and failed contact additions (5/24h to prevent enumeration attacks) (Phase 4)
19. **Simple Verification Codes**: Random 6-digit numeric codes instead of HOTP/TOTP for better email/SMS UX; industry standard for contact verification (Phase 4)
20. **Separate Verification Flow**: Users add contacts first, then explicitly request verification; provides better UX and allows batch contact addition (Phase 4)
21. **Test Database Setup**: pytest-postgresql automatically creates isolated test databases for each test with Alembic migrations. DO NOT manually create test databases or set DATABASE_URL in pytest commands - the test infrastructure handles this automatically via the `db_session` fixture in conftest.py (Phase 4)
22. **Test Authentication Pattern**: When testing authenticated endpoints, use `test_user` + `auth_headers_for_user` fixtures together. The `auth_headers_for_user` fixture generates a JWT token that matches the `test_user`'s external_id, ensuring test data and authenticated requests use the same user. DO NOT use `test_user` + `auth_headers` together as they create different users with mismatched external_ids (Phase 4)
23. **pydantic-tfl-api Integration**: The pydantic-tfl-api library is synchronous, so all TfL API calls are wrapped in `asyncio.get_running_loop().run_in_executor()` to maintain async compatibility. Client initialization uses `app_key` parameter (optional, for rate limit increase). Responses are either ApiError or success objects with `.content` attribute containing Pydantic models (Phase 5)
24. **Dynamic Cache TTL**: Cache TTL is extracted from TfL API `content_expires` field rather than hardcoded values, ensuring cache invalidation aligns with TfL's data freshness. Falls back to sensible defaults (24h for lines/stations, 2min for disruptions) when TfL doesn't provide expiry (Phase 5)
25. **Simplified Station Graph**: Graph building creates bidirectional connections between consecutive stations on each line as returned by TfL API. This is a simplified approach suitable for basic route validation; actual route sequences would provide more accuracy but require more complex TfL API integration (Phase 5)
26. **Admin Endpoint for Graph Building**: Station graph is built on-demand via admin endpoint rather than on startup to avoid blocking application initialization. Can be automated with Celery scheduler in Phase 8 (Phase 5)
27. **NullPool for Async Test Isolation**: Use `sqlalchemy.pool.NullPool` for database connections in test environments (app/core/database.py when DEBUG=true, tests/conftest.py for test fixtures). Prevents "Task attached to a different loop" errors when pytest-asyncio creates new event loops per test. This is the standard solution for async SQLAlchemy testing. Each database operation creates a fresh connection instead of pooling - acceptable performance trade-off for test reliability (Phase 5)
28. **Async Test Mocking Strategy**: Mock `asyncio.get_running_loop()` directly instead of mocking client classes in TfL service tests. Simpler approach that avoids freezegun async complications and is more explicit about async behavior. Pattern: `mock_loop = AsyncMock(); mock_loop.run_in_executor = AsyncMock(return_value=mock_response); mock_get_loop.return_value = mock_loop` (Phase 5)
