# Shared Schemas

This directory contains shared type definitions between the backend (Python/Pydantic) and frontend (TypeScript).

## Synchronization

For Phase 1, types are manually synced:
1. Define schemas in Python using Pydantic
2. Manually create equivalent TypeScript interfaces
3. Keep both in sync when making changes

Future enhancement: Automated type generation using tools like `datamodel-code-generator` or `pydantic-to-typescript`.

## Files

- `health.py` - Health check response types
- `user.py` - User-related types (stub for Phase 3)
- `common.py` - Common/utility types
