# Security & Secrets Management

## dotenvx for Secrets (Selective Encryption)

### Status
Active (supersedes python-dotenv-vault)

### Context
Originally used `python-dotenv-vault` for encrypted secret management. While functional, the `.env.vault` approach had limitations: single encrypted blob made it impossible to see which configuration keys changed in git diffs, and cloud sync workflow was complex. Additionally, encrypting all config values (including non-sensitive flags like `DEBUG=false`) reduced readability in git diffs.

### Decision
Migrated to `dotenvx` with **selective encryption** using the `SECRET_*` prefix pattern:
- Variables prefixed with `SECRET_*` are encrypted (database URLs, API keys, passwords)
- Non-secret config remains plaintext (DEBUG, OTEL_ENABLED, feature flags, etc.)
- Uses per-value inline encryption (format: `SECRET_KEY=encrypted:...`)
- Encrypted via `dotenvx encrypt -k "SECRET_*"` or `dotenvx set SECRET_KEY "value"`
- Pre-commit hook automatically encrypts SECRET_* values on commit
- Private keys stored in `.env.keys` (gitignored)
- Runtime decryption via `dotenvx run -- command` wrapper

### Consequences
**Easier:**
- **Selective encryption**: Non-secret config (DEBUG, OTEL_ENABLED) readable in git diffs
- **Improved transparency**: Can see which SECRET_* keys changed without decrypting values
- **Easier code review**: Reviewers can see config changes without needing to decrypt
- **Local security**: Secrets remain encrypted on developer machines (not just in git)
- **Flexible workflow**: Edit directly (pre-commit encrypts) OR use `dotenvx set` command
- **Better visibility**: Can see which secrets exist without decrypting
- **No Python dependency**: No `python-dotenv-vault` package needed (CLI handles everything)

**More Difficult:**
- Private keys must be managed separately (can't commit .env.keys to git)
- If private keys are lost, secrets must be regenerated
- Requires dotenvx CLI installed (not just Python package)
- Runtime wrapper needed (`dotenvx run --`) for environment injection
- Naming convention required (must prefix secrets with `SECRET_`)

### Migration Notes
- Replaced `python-dotenv-vault` Python library with `dotenvx` CLI
- Renamed secret environment variables to use `SECRET_*` prefix (e.g., `DATABASE_URL` → `SECRET_DATABASE_URL`)
- Updated `config.py` to use Pydantic `validation_alias` (field names unchanged, only env var source changed)
- Updated deployment scripts to use `DOTENV_PRIVATE_KEY_PRODUCTION` instead of `DOTENV_KEY`
- Modified CI to use `DOTENV_PRIVATE_KEY_CI` GitHub secret
- Pre-commit hooks updated to run `dotenvx encrypt -k "SECRET_*"` (selective encryption)
- Dockerfile updated to install dotenvx and wrap CMD with `dotenvx run --`
- Test files updated to use new `SECRET_DATABASE_URL` variable name

---

## python-dotenv-vault for Secrets (SUPERSEDED)

### Status
Superseded by dotenvx (see above)

### Context
Originally chose SOPS/age for encrypted secret management, but configuration was complex and required managing age keys separately. Needed a simpler solution that integrates with the Python ecosystem and supports local encryption without cloud services.

### Decision
Use `python-dotenv-vault` for encrypted secret management. Secrets stored in `.env.vault` file (encrypted), decrypted at runtime. Pre-commit hooks auto-rebuild `.env.vault` when `.env` changes. No cloud service required (locally managed encryption key).

### Consequences
**Easier:**
- Simpler setup than SOPS/age (no separate key management)
- Integrates directly with Python ecosystem
- Pre-commit hooks ensure `.env.vault` stays in sync
- No cloud service dependency (offline capable)
- Standard `.env` file format (familiar to developers)

**More Difficult:**
- Encryption key must be managed separately (can't commit to git)
- If encryption key is lost, secrets must be regenerated
- Less mature than SOPS (smaller community)

---

## DB Credential Separation

### Status
Active

### Context
Application should run with minimal database permissions (principle of least privilege). If application is compromised, attacker shouldn't be able to drop tables or modify schema. However, migrations require elevated permissions.

### Decision
Application runs with limited database user (SELECT, INSERT, UPDATE, DELETE only). Migrations run in separate CI/init container with admin database access. Production app cannot ALTER tables or DROP database.

### Consequences
**Easier:**
- Principle of least privilege enforced
- Compromised application can't modify schema
- Clear separation of concerns (app vs migrations)
- Audit trail of schema changes (migrations only in CI)

**More Difficult:**
- Need two sets of database credentials (app user, admin user)
- CI must have access to admin credentials
- Cannot run migrations from running application (must restart or use separate job)

---

## Required Config Validation

### Status
Active

### Context
Applications with misleading defaults (e.g., `DATABASE_URL = "sqlite:///"`) can start successfully but fail silently or behave incorrectly. Better to fail fast with clear error messages.

### Decision
Critical configuration values (`DATABASE_URL`, `REDIS_URL`, `ALLOWED_ORIGINS`) must be explicitly provided - no defaults. Application uses `require_config()` utility to validate configuration on startup and fails with clear error message if required values are missing.

### Consequences
**Easier:**
- Fail fast with clear error messages
- No silent failures due to wrong configuration
- Developers immediately know what config is missing
- Prevents accidental use of wrong database (e.g., dev database in production)

**More Difficult:**
- Cannot start application without all required config (but this is desired behavior)
- Need to document all required environment variables
- More verbose `.env.example` file

---

## Rate Limiting Strategy

### Status
Active

### Context
Contact verification and addition endpoints are vulnerable to abuse: attackers could spam verification codes or enumerate valid emails/phones by observing response times or error messages.

### Decision
Implement two-tier rate limiting: (1) Verification codes: 3 per hour per user (prevents spam), (2) Failed contact additions: 5 per 24 hours per user (prevents enumeration attacks). Rate limits reset on successful verification. Store rate limit counters in Redis.

### Consequences
**Easier:**
- Prevents verification code spam
- Prevents enumeration attacks (can't rapidly test many contacts)
- Protects email/SMS providers from abuse
- Legitimate users unlikely to hit limits (3 codes/hour is generous)

**More Difficult:**
- Need to maintain rate limit state in Redis
- Edge cases to handle (what if Redis is down?)
- Users who genuinely need more codes must wait (but this is rare)

---

## Frontend Configuration in JSON

### Status
Active

### Context
Frontend applications running in browsers cannot securely store secrets. Any configuration embedded in the frontend bundle is publicly visible. Need a clear pattern that prevents accidentally committing secrets to frontend config.

### Decision
Frontend configuration is stored in plain JSON files (not `.env` files). This makes it explicit that frontend config contains NO secrets. All configuration in frontend is public and can be safely committed to git. Any secrets needed by frontend (API keys, tokens) must be obtained from the backend after authentication.

### Consequences
**Easier:**
- Clear signal that frontend has no secrets (JSON format instead of .env)
- No risk of accidentally committing secrets to frontend config
- Configuration can be safely version-controlled
- No build-time environment variable complications
- Standard JSON parsing in JavaScript (no special libraries needed)

**More Difficult:**
- Different config pattern than backend (.env vs JSON)
- Must obtain any sensitive values from backend after login
- Cannot use environment variables for frontend config (but this is correct behavior)
