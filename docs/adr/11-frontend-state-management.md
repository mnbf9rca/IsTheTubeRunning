# Frontend State Management

## Complex State Management Pattern

### Status
Active

### Context
Complex components with 8+ state variables and 10+ handlers become error-prone with scattered validation and state transitions. SegmentBuilder had recurring bugs (#56, #86, #89, #90, #93) from duplicated logic, forgotten state updates, and tight coupling to React hooks making testing difficult (56% coverage).

### Decision
Extract state logic into pure, testable functions in a layered architecture: `types.ts` (state types, enums), `validation.ts` (pure validation functions), `actions.ts` (business logic), `transitions.ts` (state machine logic), `hooks.ts` (React integration). Implement gradually: validation first, then logic, then state machine. Each layer must have 100% test coverage before moving to next. Component becomes thin presentation layer.

### Consequences
**Easier:**
- 100% test coverage on validation and logic (pure functions are easy to test)
- No duplication (validation defined once, used everywhere)
- Safe refactoring (tests catch regressions)
- Clear separation of concerns (types, validation, logic, presentation)
- Debugging (each layer can be tested in isolation)
- Future changes (modify logic without touching React code)

**More Difficult:**
- More files to maintain (5-6 files vs 1 monolithic component)
- Initial time investment (extract and test each layer)
- Learning curve (team must understand architecture)
- Overkill for simple components (use only when complexity justifies it)

---

## Pure Function Architecture

### Status
Active

### Context
Testing logic coupled to React hooks (useState, useEffect) is difficult and achieves low coverage. Need way to test complex logic in isolation without mocking React.

### Decision
Extract all business logic and validation into pure functions (no side effects, same input → same output). Pure functions are in separate files, tested to 100% coverage. React component calls pure functions and manages only UI state. Pattern: `const result = validateFoo(input); if (!result.valid) { setError(result.error); return }`

### Consequences
**Easier:**
- 100% test coverage (pure functions are trivial to test)
- Fast tests (no React rendering, no mocks)
- Reusable logic (can call from anywhere)
- Predictable behavior (no hidden state)

**More Difficult:**
- Must pass all context as parameters (no closure over component state)
- More verbose at call sites (function call + check result + set error)
- Need clear contracts (types, JSDoc, tests)

---

## When to Apply This Pattern

### Status
Active

### Context
Not all components need this architecture. Need criteria for when complexity justifies extraction.

### Decision
Apply pattern when component has **3+ of these signals**: (1) 8+ useState calls, (2) 10+ handler functions, (3) Validation logic duplicated 2+ times, (4) Bugs from forgotten state updates, (5) Test coverage below 60%, (6) useEffect dependencies causing subtle bugs. Simple components (1-2 state variables, 3-4 handlers) should stay as single-file components.

### Consequences
**Easier:**
- Clear decision criteria (when to refactor vs keep simple)
- Avoid premature abstraction (YAGNI principle)
- Consistent patterns across complex components

**More Difficult:**
- Requires judgment call (3+ signals is guideline, not rule)
- Easy to over-engineer simple components
- May need to refactor later if component becomes complex

---

## Implementation Guidelines

### Status
Active

### Context
Full refactoring at once is risky. Need incremental approach that ships working code.

### Decision
Implement in phases over 4 PRs: (1) Extract validation + types (eliminate duplication), (2) Extract business logic (segment building, deletion), (3) Extract state transitions (state machine), (4) Create custom hook (integrate layers). Each PR is independently useful and fully tested. Test after each change. Update GitHub issue after each phase.

### Consequences
**Easier:**
- Ship value incrementally (each PR improves codebase)
- Low risk (small changes with full test coverage)
- Easy to review (focused PRs)
- Can pause between phases (each PR is complete)

**More Difficult:**
- More PRs to manage (4 instead of 1)
- Each PR must maintain existing behavior (no breaking changes)
- Need discipline to not skip testing phases

---

## Testing Requirements

### Status
Active

### Context
Pure functions enable 100% coverage, but need standards to maintain quality.

### Decision
Each extracted module must have **100% statement and branch coverage** before being used in component. Integration tests (existing component tests) must all pass after refactoring. Coverage targets: pure functions (validation, logic, transitions) = 100%, custom hooks = 90%+, components = 85%+. Test files named `*.test.ts` for unit tests, `*.test.tsx` for component tests.

### Consequences
**Easier:**
- High confidence in correctness (every branch tested)
- Safe to refactor (tests catch regressions)
- Documentation through tests (tests show how to use functions)
- CI catches coverage drops (enforce with GitHub Actions)

**More Difficult:**
- Takes time to write comprehensive tests (2-3 hours per module)
- Must test edge cases (empty arrays, null values, boundaries)
- 100% target is strict (must test error paths too)

---

## Route Builder State Machine Pattern

### Status
Active (Implemented in Phase 10 PR3)

### Context
SegmentBuilder component manages complex multi-step route creation workflow with 8+ state variables and 15+ handlers. Initial implementation had recurring bugs from improper state transitions causing UI inconsistencies (stations disappearing, buttons in wrong states).

### Decision
Build custom state machine with pure functions instead of using libraries like XState. Extract all logic into separate testable modules: validation, segments manipulation, state transitions, and React integration hook. Component becomes thin presentation layer.

### Consequences
**Easier:**
- Debugging and testing (pure functions, 100% coverage)
- Safe refactoring (tests catch regressions)
- Code reuse across components
- Clear workflow (explicit state machine)

**More Difficult:**
- More files to navigate (6 files vs 1)
- Learning curve for pattern
- Risk of over-engineering simple forms
