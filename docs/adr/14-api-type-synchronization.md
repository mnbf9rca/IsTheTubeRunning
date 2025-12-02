# API Type Synchronization

## Status
Active

## Context
The backend uses Python with Pydantic models for request/response schemas, while the frontend uses TypeScript. Maintaining manually duplicated type definitions in both codebases leads to:
- Type drift when backend schemas change
- Manual effort to keep types synchronized
- Runtime errors from schema mismatches
- No compile-time guarantee that frontend types match backend API

FastAPI automatically generates OpenAPI specifications from Pydantic models, providing a machine-readable contract. Several approaches were considered:
1. **Runtime code generation** - Generate types on server startup, but requires running backend to get types
2. **Pre-commit hooks only** - Automatically regenerate on commit, but no verification that types are committed
3. **CI verification only** - Verify in CI, but easy to forget manual regeneration
4. **Hybrid approach** - Manual regeneration + CI verification with committed spec

## Decision
Use openapi-typescript to automatically generate TypeScript types from the backend OpenAPI specification, following a hybrid approach:

**Type Generation:**
- Backend generates OpenAPI spec statically via `backend/scripts/generate_openapi.py`
- OpenAPI spec committed to repository at `backend/openapi.json`
- Frontend generates TypeScript types from committed spec using openapi-typescript
- Generated types formatted with prettier to match project style
- Types committed to repository at `frontend/src/types/api-generated.ts`

**Automation:**
- Manual regeneration: Run `npm run generate-types` when backend schemas change
- CI verification: `npm run check-types-sync` fails build if types are out of sync
- Pre-commit hooks enforce code quality but don't auto-generate types

**Type Organization:**
- Generated types in `frontend/src/types/api-generated.ts` (auto-generated, do not edit)
- Barrel file at `frontend/src/types/index.ts` re-exports with type aliases for backward compatibility
- Frontend-only types remain in `frontend/src/lib/api.ts` (e.g., `RecentLogsParams`, `AdminUsersParams`)

## Consequences

**Easier:**
- Single source of truth for API contracts (backend Pydantic models)
- TypeScript compilation errors immediately reveal API contract mismatches
- Type safety across full stack prevents runtime errors
- Generated types reveal legitimate type safety issues (undefined vs null handling)
- CI verification prevents merging code with stale types
- No manual type duplication or maintenance

**More Difficult:**
- Requires manual regeneration when backend schemas change (documented in workflow)
- Adds build step to CI pipeline (minimal overhead)
- Generated types may need nullish coalescing in frontend code (`?? null` for undefined → null)
- Breaking changes to backend schemas now cause TypeScript compilation errors (this is a feature, not a bug)
