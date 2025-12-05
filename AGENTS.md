# Project Guidelines

## ⚠️ CRITICAL RULES

**Subagents frequently violate these rules. Read carefully.**

### Environment & Execution
- ⚠️ **ALWAYS** use `dotenvx run -- uv run` in `/backend` directory
  - **NEVER** use naked `python` or `python3` commands
  - **NEVER** manually set `PYTHONPATH` environment variable
- ⚠️ Database name comes from config files
  - **NEVER** assume database is called `testdb` or `testrun`
  - Use actual connection details from `backend/.env` (encrypted with dotenvx)
- ⚠️ Use `./test-runner.sh` for frontend tests
  - **NEVER** run `npm test` directly (triggers consent prompts)
- ⚠️ Don't pipe scripts to `python` command (triggers sandbox protection)
  - Instead: create temporary script file, execute it, then delete it
  - try to avoid using `/tmp` - use project directory if possible - create a temp folder if needed but ensure cleanup
- ⚠️ **NEVER** start processes detached
  - No `nohup`, no `&`, no daemon mode
  - Always use background bash processes for FastAPI, Node, Celery, Beat
  - Use foreground processes in background shells for proper log access

### Code Quality
- ⚠️ **NEVER** use `# noqa` to suppress linting errors
  - Refactor the code instead, especially for complexity warnings (PLR0912, PLR0915)
  - Use pure functions to reduce complexity
  - Only exception: PLC0415 for necessary circular import prevention (document rationale)
- ⚠️ **NEVER** use `Any` types in internal code
  - Use precise types for all internal functions and classes
  - `Any` only allowed for 3rd party library wrappers where precise types are impossible
- ⚠️ Use `ast-grep` for code modifications
  - **NEVER** use `sed` or `awk` - they corrupt complex files

### Credentials & Testing
- ⚠️ Credentials **ARE** available - check `.env` files
  - Backend: `backend/.env` (encrypted with dotenvx)
  - Backend: Use `app.cli` to create users for API calls or assign/remove admin roles
  - Frontend: `frontend/.env` (includes Playwright test credentials)
  - **Don't give up on testing** - credentials exist for API testing and UI testing

---

## Principles

- This is a hobby project - prefer KISS, DRY, YAGNI over enterprise patterns
- Read relevant ADRs in `docs/adr/` before starting work
- Consider whether your changes warrant updating the ADRs; include this as a task if needed

---

## Coding Standards

### Type Safety
- No `Any` types for internal code - use precise types
- `Any` only allowed for 3rd party library wrappers where precise types are not possible
- Only use `if TYPE_CHECKING:` conditional imports where absolutely necessary to prevent circular imports
- We're on Python 3.14

### Linting & Code Quality
- Never suppress linting errors if it's possible to fully resolve them
- Where necessary (e.g. PLC0415 for circular imports), document the rationale in a comment
- **Never** use `# noqa: PLR0912, PLR0915` or similar to suppress complexity warnings
  - Refactor the function to reduce complexity without suppressing linting errors
  - Implement by refactoring to pure functions where possible

### Test Coverage Requirements
- Backend: 100% code coverage on new code
- Frontend: 85% code coverage on new code
- Maintain existing code coverage levels

---

## Testing

### Running Tests
- **Backend:** `dotenvx run -- uv run pytest` (from `/backend` directory)
- **Frontend:** `./test-runner.sh` (avoids consent prompts) or `./safe-test-runner.sh` (catches memory leaks but slightly slower)
- Verify all pre-commit hooks pass: `pre-commit run --all-files`

### Test Validation
- Verify that fixes do not introduce regressions
- Consider using Playwright MCP to test UI flow, components, etc.
  - Credentials available in `frontend/.env`

---

## Git Workflow

### Branch Management
- If on `main`: pull latest changes and create a new branch
- If NOT on `main`: ask user whether to "work on current branch" or "checkout main, pull latest, and create new branch" BEFORE beginning work

### Commits
- Never commit or push until the user gives you an explicit instruction
- Never amend commits
- Do not create new GitHub labels

### Pull Requests
- Warn the user if the resulting PR is likely to be too large to review easily
- Suggest breaking it into smaller PRs

### Issue Tracking
- If working on an issue, update the GitHub issue as you progress, not at the end
- If your plan changes, update the issue with the new plan as you go
- Prefer editing one comment over posting several comments tracking progress

---

## Development Environment

### Running Services
Start these as background bash processes (never detached/nohup):
- Backend API
- Celery worker
- Celery beat
- Frontend dev server

### Secrets & Environment
- In `/backend`, always use `dotenvx run -- uv run` (never naked `python`)
- `DATABASE_URL` is already set in config - no need to set it manually
- Don't pipe scripts to `python` (triggers sandbox) - create temp script, run it, delete it

### Database Access
- Use `psql` to check database tables directly
- Connection details in `backend/.env` (encrypted with dotenvx)
- Note: database is NOT called `testdb` or `testrun` - use actual name from config

### Production Server Access
**Always use the script to get the VM IP - never hardcode it.**

When running on local development machine, connect to remote server:
```bash
# Get the production VM IP dynamically (sources deploy/azure-config.json)
PROD_IP=$(./scripts/get-prod-vm-ip.sh)

# Connect via SSH
ssh -i ~/.ssh/isthetube-deploy-key deployuser@$PROD_IP
```

Notes:
- psql is not installed on the remote host
- For database access, either:
  - Use port forwarding: `ssh -L 5432:localhost:5432 -i ~/.ssh/isthetube-deploy-key deployuser@$PROD_IP`
  - Use psql inside the docker container on the remote host
- Consider local database port conflicts when forwarding

### Local OTEL Collector (optional)
If you want to run a local OTEL collector:
1. Set `OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318/v1/traces"`
2. Run `{projectroot}/scripts/otelcol --config {projectroot}/scripts/otel-config.yaml`
3. Watch the output

---

## Tools & Resources

### Code Search & Modification
- Use `ast-grep` CLI tool for code structural search, lint, and rewriting
- Prefer `ast-grep` over `grep`/`rg` for finding code locations and making changes

### User Management
- Use `app.cli` to create users for API calls or assign/remove admin roles
- See README.md for details

### GitHub
- Use `gh` command for all GitHub-related tasks
- Working with issues, pull requests, checks, releases, etc.
