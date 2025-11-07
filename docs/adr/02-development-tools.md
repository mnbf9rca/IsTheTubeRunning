# Development Tools & Code Quality

## uv for Python Package Management

### Status
Active

### Context
Traditional Python package management with `pip` and `virtualenv` is slow and lacks modern features like lockfiles and dependency resolution. Need a faster, more reliable solution.

### Decision
Use `uv` for all Python package management. All backend commands must use `uv run` prefix. Never use naked `python` or `pip` commands.

### Consequences
**Easier:**
- Extremely fast package installation and resolution
- Built-in virtual environment management
- Lockfile support for reproducible builds
- Modern CLI similar to npm/pnpm
- Better dependency conflict resolution

**More Difficult:**
- Team members must install `uv` (additional setup step)
- Less familiar than `pip` (smaller community, fewer Stack Overflow answers)
- Must remember to prefix commands with `uv run`

---

## Tailwind CSS v4

### Status
Active

### Context
Need a modern, utility-first CSS framework for frontend. Tailwind CSS v4 introduces significant improvements over v3, including better performance and native CSS features.

### Decision
Use Tailwind CSS v4 (not v3). Configuration and syntax differ significantly from v3. Use Context7 or WebFetch tools to get current v4 documentation when needed.

### Consequences
**Easier:**
- Latest features and performance improvements
- Native CSS features (better browser support)
- Improved developer experience with v4 tooling
- Future-proof choice (v4 is current)

**More Difficult:**
- Limited online resources (many tutorials still use v3)
- Migration guides from v3 may not directly apply
- Need to reference v4-specific documentation
- Breaking changes from v3 if copying code snippets

---

## shadcn/ui Component Library

### Status
Active

### Context
Need a component library for React frontend that is lightweight, customizable, and doesn't bloat bundle size. Traditional component libraries like Material-UI are heavy and opinionated.

### Decision
Use shadcn/ui (canary version for React 19 support) - a collection of copy-paste components built on Radix UI primitives and styled with Tailwind CSS.

### Consequences
**Easier:**
- Full control over component code (components live in your codebase)
- Lightweight (only install components you use)
- Highly customizable (modify component code directly)
- Built on accessible Radix UI primitives
- No runtime dependency on a component library package

**More Difficult:**
- Components are copied into codebase (more files to maintain)
- Updates require manually copying new component versions
- No centralized component package updates
- Using canary version (less stable than production releases)
