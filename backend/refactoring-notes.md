# Refactoring Notes - Route → UserRoute

**Purpose**: Shared knowledge base for agents working on issue #175. Delete this file when Phase 9 is complete.

## Current State (After Phase 3)

✅ **Completed**:
- Phase 1-3: Database tables renamed
  - `routes` → `user_routes`
  - `route_segments` → `user_route_segments`
  - `route_schedules` → `user_route_schedules`
  - `route_station_index` → `user_route_station_index`

❌ **Not Started**:
- Phase 4: Model class renames (Route, RouteSegment, RouteSchedule)
- Phase 5: Service class renames (RouteService, RouteIndexService)
- Phase 6: RouteStationIndex model rename
- Phase 7: API schema renames (RouteResponse, etc.)
- Phase 8: Line.routes → Line.route_variants
- Phase 9: Documentation updates

## Test Status
- All tests passing: 1057 tests ✓
- Coverage: 95.87% ✓
- Type checking: mypy passes ✓

## Learnings from Phase 1-3

### What Worked Well
1. **Modifying existing migrations** instead of creating new ones (database can be purged)
2. **Vertical slicing** - changing one table at a time across all files
3. **Immediate testing** after each phase prevents error accumulation

### ast-grep Patterns That Work
```bash
# Find all class definitions
ast-grep --pattern 'class $NAME' backend/app/

# Find all imports from a module
ast-grep --pattern 'from $MODULE import $$$' backend/

# Find type hints
ast-grep --pattern ': $TYPE'
ast-grep --pattern '-> $TYPE'
ast-grep --pattern 'list[$TYPE]'

# Find instantiations
ast-grep --pattern '$CLASS($$$)'
```

### Common Pitfalls to Avoid
1. **Don't use sed/awk** - too error-prone, misses edge cases
2. **Always read files first** before editing - understand context
3. **Use Edit tool, not Write** for existing files
4. **Check TYPE_CHECKING imports** - these need updating too for circular import prevention
5. **Foreign keys need manual updating** - ast-grep won't catch string literals in ForeignKey()

## Ground Rules for All Phases

1. **Read this file FIRST** before starting your phase
2. **Use ast-grep extensively** for finding code locations
3. **Update ALL test files** - no skipping or bypassing tests allowed
4. **Verify with ast-grep** after changes that old names don't exist
5. **Run full test suite** - all 1057+ tests must pass
6. **Maintain >95% coverage** - check with pytest --cov
7. **Type safety** - mypy --strict must pass
8. **Pre-commit hooks** - must pass before committing
9. **Append your learnings** to this file for the next agent
10. **No backward compatibility hacks** - complete renames only

## Success Criteria Template

Each phase must achieve:
- [ ] All renames completed (use ast-grep to verify)
- [ ] All imports updated across codebase
- [ ] `cd backend && uv run mypy app` passes
- [ ] `cd backend && uv run pytest -v` - ALL tests pass
- [ ] `cd backend && uv run pytest --cov=app --cov-report=term-missing` - >95% coverage
- [ ] `pre-commit run --all-files` passes
- [ ] Learnings appended to this file
- [ ] Changes committed with clear message

## Phase-Specific Notes

### Phase 4: Model Classes
**Files to focus on**:
- `backend/app/models/route.py` - class definitions
- `backend/app/models/__init__.py` - exports
- All imports across ~30+ files

**Key changes**:
- `class Route` → `class UserRoute`
- `class RouteSegment` → `class UserRouteSegment`
- `class RouteSchedule` → `class UserRouteSchedule`

**Don't forget**:
- Relationship back_populates references
- TYPE_CHECKING imports
- Type hints in function signatures

### Phase 5: Service Classes
**Files to focus on**:
- `backend/app/services/route_service.py`
- `backend/app/services/route_index_service.py`
- API endpoints (~2 files)
- Celery tasks (~1 file)

**Key changes**:
- `class RouteService` → `class UserRouteService`
- `class RouteIndexService` → `class UserRouteIndexService`
- All instantiations: `RouteService(db)` → `UserRouteService(db)`

### Phase 6: RouteStationIndex
**Files to focus on**:
- `backend/app/models/route_index.py`
- `backend/app/models/__init__.py`
- Services and tasks using this model

**Key change**:
- `class RouteStationIndex` → `class UserRouteStationIndex`

### Phase 7: API Schemas
**Files to focus on**:
- `backend/app/schemas/routes.py` - 8 schema classes
- `backend/app/api/routes.py` - type hints only
- **DO NOT** change endpoint paths (`/routes` stays `/routes`)

**Key changes**: All Route* schema → UserRoute* schema

### Phase 8: Line.routes → Line.route_variants
**Files to focus on**:
- Migration that added `Line.routes` column
- `backend/app/models/tfl.py`
- Services/tasks referencing `line.routes`

**Key change**: `Line.routes` → `Line.route_variants` (clarifies TfL data vs user routes)

### Phase 9: Documentation
**Files to focus on**:
- `docs/adr/03-database.md`
- Comments and docstrings
- **DELETE THIS FILE** when complete

---

## Learnings Log

### Phase 4: Model Class Renames (COMPLETE)
- **What worked**:
  - Using Edit tool with `replace_all=true` for consistent patterns (e.g., `Route(` → `UserRoute(`)
  - Systematically updating imports first, then type hints, then usages
  - ast-grep for verification of complete replacement
  - Mypy caught all type-related issues immediately

- **What didn't**:
  - Initial approach of doing blanket `replace_all` for `Route` accidentally renamed service classes (RouteService → UserRouteService) and schema names which shouldn't have been changed in Phase 4
  - `replace_all` on already-replaced imports created double-replacements (UserRoute → UserUserRoute)
  - Missed references like `select(Route)` and `Route.` that weren't caught by `Route(` pattern
  - Had to manually fix test files with multiple patterns (`-> Route:`, `route: Route`, `Route.`, `select(Route)`)

- **Gotchas**:
  - **Service class names should NOT be renamed in Phase 4** (that's Phase 5) - had to revert RouteService and RouteIndexService
  - **Schema names should NOT be renamed in Phase 4** (that's Phase 7) - had to revert CreateUserRouteRequest back to CreateRouteRequest
  - **RouteStationIndex should NOT be renamed** - that's Phase 6
  - Type annotations in function signatures need separate replacements: `-> Route:`, `route: Route`
  - SQLAlchemy queries need updates: `select(Route)`, `Route.id`, etc.
  - Must read files before using Edit tool (encountered multiple "file not read" errors)

- **Time taken**: ~2 hours (including fixing double-replacements and missed patterns)

### Phase 5: Service Class Renames (COMPLETE)
- **What worked**:
  - Using `git mv` to rename files preserved git history
  - Edit tool with `replace_all=true` was very effective for consistent patterns like `RouteService(` and `RouteIndexService(`
  - Systematic approach: rename files → update class definitions → update imports → update instantiations → update patch decorators → rename test files
  - ast-grep verification at the end confirmed zero old references remained
  - Patch decorator updates in test files were straightforward with replace_all

- **What didn't**:
  - Some minor comments in test files were missed initially but caught during verification
  - Test class names (e.g., `class TestRouteIndexService:`) weren't caught by initial instantiation patterns

- **Gotchas**:
  - **File imports must be updated before instantiations** - otherwise you get import errors
  - **Patch decorators use string paths** - must update both module name (`route_service` → `user_route_service`) AND class name
  - **Test class names** need manual updating (not caught by `ServiceName(` pattern)
  - **Cross-imports** between services (user_route_service imports UserRouteIndexService) need updating
  - **Comments and docstrings** also need updates, not just code
  - **Ruff auto-fixes import ordering** - pre-commit will reorder imports after updates

- **Key patterns used**:
  - `replace_all=true` for: `RouteService(`, `RouteIndexService(`, patch decorator paths
  - Individual replacements for: imports, class definitions, docstrings, test class names
  - ast-grep verification: `ast-grep --pattern 'class RouteService' app/ tests/` (should return nothing)

- **Time taken**: ~45 minutes (including quality checks)

### Phase 6: RouteStationIndex → UserRouteStationIndex + File Renaming (COMPLETE)
- **What worked**:
  - Using `replace_all=true` was effective for bulk replacements across files
  - `git mv` preserved file history perfectly for route.py → user_route.py and route_index.py → user_route_index.py
  - ast-grep verification (`ast-grep --pattern 'RouteStationIndex'`) confirmed zero old references remained
  - Systematic approach: class rename → import updates → file renames → import updates again
  - Pre-commit hooks (ruff) auto-fixed import ordering after bulk changes (18 fixes)
  - All validation passed: mypy (55 files ✓), pytest (1057 tests ✓), coverage (95.87% ✓), pre-commit (✓)

- **What didn't**:
  - Initial `replace_all` in service files accidentally double-replaced imports: `RouteStationIndex` → `UserUserRouteStationIndex`
  - Had to manually fix the import lines in 3 service files (user_route_index_service, alert_service, tasks)

- **Gotchas**:
  - **CRITICAL**: When using `replace_all=true`, it replaces ALL occurrences including already-replaced text
    - Example: Import statement already had `UserRouteStationIndex`, replace_all changed it to `UserUserRouteStationIndex`
    - Solution: Use targeted single replacements for import statements, use replace_all for code references
  - **File renaming scope expansion**: User asked to rename model files for consistency after seeing class renames complete
    - route.py → user_route.py, route_index.py → user_route_index.py (26 files updated with new imports)
    - This was the right call for complete consistency - no half-measures
  - **TYPE_CHECKING imports** must be updated in circular import prevention blocks
  - **Ruff auto-reordering** of imports is expected after bulk updates - not an error, just run pre-commit
  - **Comments in cross-references** like notification.py line 21 reference the file name, update those too

- **Key learnings**:
  - File renaming is cheap when done with `git mv` - preserves history, worth doing for consistency
  - When user suggests scope expansion mid-task, evaluate if it makes sense (in this case: yes, complete the refactoring properly)
  - `replace_all` is powerful but dangerous - always read files first and understand what will be replaced
  - Verify with ast-grep before AND after changes

- **Time taken**: ~35 minutes (class rename) + ~25 minutes (file renames + import updates) = ~60 minutes total

### Phase 7: API Schema Renames (COMPLETE)
- **What worked**:
  - Systematic approach: schema definitions → API endpoints → service layer → test files
  - Using targeted Edit tool calls instead of blanket `replace_all` avoided double-replacement errors
  - Renaming ALL 11 schemas (not just the 8 mentioned in issue) for complete consistency
  - ast-grep verification confirmed zero old schema names remained
  - All validation passed: mypy (55 files ✓), pytest (1057 tests ✓), coverage (95.87% ✓), pre-commit (✓)
  - OpenAPI schema auto-update confirmed new names appear in /docs
  - Endpoint paths confirmed unchanged (all still use `/routes` - no breaking API changes)

- **What didn't**:
  - Issue description had incorrect "before" names (said `RouteScheduleResponse` but actual was `ScheduleResponse`)
  - Issue scope was unclear (said 8 schemas, but 11 existed in the file)
  - User questioned verbose naming (`UserRouteScheduleResponse` vs shorter alternatives)

- **Gotchas**:
  - **Schema count mismatch**: Issue said 8 schemas, but actual codebase had 11. Decision: rename all 11 for consistency
  - **Issue description inaccuracy**: Listed `CreateRouteSegmentRequest` but actual name was `SegmentRequest`
  - **Naming verbosity concern**: User raised concern about `UserRouteScheduleResponse` being too verbose
    - Decision: Continue with verbose naming for consistency with models (`UserRouteSchedule`) and services (`UserRouteService`)
    - Rationale: Schema response names mirror the model names they serialize
  - **TfL schema collision**: `RouteSegmentRequest` exists in `app.schemas.tfl` - must NOT be renamed (it's for TfL API, not user routes)
    - Used ast-grep carefully to avoid changing the wrong schema
    - Checked imports to ensure only `app.schemas.routes` imports were updated
  - **API endpoint paths unchanged**: Router prefix and decorators stay `/routes` - only type hints and response_model updated
    - Verified with OpenAPI path inspection
  - **Self-references in validators**: Methods like `validate_time_range(self) -> "CreateScheduleRequest"` need updating to new name

- **Key patterns used**:
  - Targeted Edit calls for each class definition (no blanket replace_all)
  - Single import statement update per file (alphabetically sorted by ruff)
  - ast-grep verification: `ast-grep --pattern 'CreateRouteRequest'` (should return nothing)
  - OpenAPI verification: Check schemas and paths in generated docs

- **Verification checklist**:
  1. ast-grep: No old schema names found ✓
  2. mypy: All type checks pass ✓
  3. pytest: All 1057 tests pass ✓
  4. coverage: 95.87% maintained ✓
  5. pre-commit: All hooks pass ✓
  6. OpenAPI schemas: New names present ✓
  7. Endpoint paths: Unchanged (/routes preserved) ✓

- **Time taken**: ~35 minutes (research, rename, verification)

- **Key learnings**:
  - Always clarify scope when issue description doesn't match reality (asked user about 8 vs 11 schemas)
  - User feedback on naming conventions is important - explain rationale for consistency
  - Verify both positive (new names appear) and negative (old names gone, paths unchanged) outcomes
  - Schema renames impact OpenAPI docs - always verify /docs endpoint
  - Issue descriptions can be inaccurate - trust the codebase, not the issue text

### Phase 8: [Agent to fill in]
- **What worked**:
- **What didn't**:
- **Gotchas**:
- **Time taken**:

### Phase 9: Documentation Complete
**Remember**: DELETE THIS FILE when Phase 9 is complete!
