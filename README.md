# IsTheTubeRunning

A TfL (Transport for London) disruption alert system that notifies users of service interruptions on their regular routes.

## Project Status

**Phase 1: Project Foundation** ✅ Complete
**Phase 2: Database Models & Migrations** ✅ Complete
**Phase 3: Auth0 Integration** 🚧 In Progress

See [implementation_plan.md](./implementation_plan.md) for the full roadmap.

## Tech Stack

### Backend
- **Python 3.14** with **uv** for package management
- **FastAPI** 0.115+ for API
- **SQLAlchemy 2.0** (async) + **Alembic** for database
- **PostgreSQL 18** for data storage
- **Redis 8.2.1** for caching and message queue
- **Celery 5.4** for background jobs
- **pytest** for testing
- **ruff** + **mypy** for code quality

### Frontend
- **React 19** + **TypeScript 5.9**
- **Vite 7** for build tooling
- **Tailwind CSS 3.4** for styling
- **shadcn/ui** for UI components
- **React Router** for navigation
- **Vitest** for testing

### Infrastructure
- **Docker Compose** for local development
- **PostgreSQL** + **Redis** containerized services
- **Nginx** for reverse proxy (production)
- **GitHub Actions** for CI/CD
- **Azure VM** for deployment (Phase 12)

## Project Structure

```
IsTheTubeRunning/
├── backend/           # FastAPI application
│   ├── app/
│   │   ├── api/       # API endpoints
│   │   ├── core/      # Core configuration
│   │   ├── models/    # Database models
│   │   ├── services/  # Business logic
│   │   └── main.py    # FastAPI app
│   ├── tests/         # Backend tests
│   ├── alembic/       # Database migrations
│   └── pyproject.toml # Python dependencies
├── frontend/          # React application
│   ├── src/
│   │   ├── components/ # React components
│   │   ├── pages/      # Page components
│   │   ├── lib/        # Utilities
│   │   └── test/       # Test utilities
│   ├── package.json    # Node dependencies
│   └── vite.config.ts  # Vite configuration
├── shared/            # Shared types
│   ├── schemas/       # Python/Pydantic models
│   └── types/         # TypeScript interfaces
├── docker/            # Docker configurations
│   ├── nginx/         # Nginx config
│   └── scripts/       # Deployment scripts
├── .github/workflows/ # CI/CD pipelines
└── docker-compose.yml # Local development services
```

## Local Development Setup

### Prerequisites

- **Python 3.14+**
- **Node.js 24 LTS**
- **Docker** with Colima (macOS) or Docker Desktop
- **uv** for Python package management
- **npm** for Node.js packages

### Backend Setup

1. **Install dependencies:**
   ```bash
   cd backend
   uv sync
   ```

2. **Start Docker services (PostgreSQL + Redis):**
   ```bash
   # From project root
   docker-compose up -d
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run the backend:**
   ```bash
   cd backend
   uv run uvicorn app.main:app --reload
   ```

   Backend will be available at http://localhost:8000

5. **Run tests:**
   ```bash
   uv run pytest
   ```

6. **Code quality:**
   ```bash
   # Format code
   uv run ruff format .

   # Lint code
   uv run ruff check .

   # Type check
   uv run mypy app
   ```

### Frontend Setup

1. **Install dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Default: VITE_API_URL=http://localhost:8000
   ```

3. **Run the frontend:**
   ```bash
   npm run dev
   ```

   Frontend will be available at http://localhost:5173

4. **Run tests:**
   ```bash
   npm run test        # Watch mode
   npm run test:ui     # UI mode
   npm run test:run    # Run once
   ```

5. **Build for production:**
   ```bash
   npm run build
   ```

### Docker Services

Start all development services:
```bash
docker-compose up -d
```

Stop services:
```bash
docker-compose down
```

View logs:
```bash
docker-compose logs -f
```

## API Endpoints

### Health Checks
- `GET /` - Root information
- `GET /health` - Health check
- `GET /ready` - Readiness check

### Authentication (Phase 3)
- `GET /api/v1/auth/me` - Get current user (auto-creates on first login)

### API Documentation
- `http://localhost:8000/docs` - Swagger UI (includes authentication)
- `http://localhost:8000/redoc` - ReDoc

## Development Workflow

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes and test:**
   ```bash
   # Backend
   cd backend && uv run pytest

   # Frontend
   cd frontend && npm run test:run
   ```

3. **Lint and format:**
   ```bash
   # Backend
   cd backend && uv run ruff format . && uv run ruff check .

   # Frontend
   cd frontend && npm run lint
   ```

4. **Commit and push:**
   ```bash
   git add .
   git commit -m "feat: your feature description"
   git push origin feature/your-feature-name
   ```

5. **Create a pull request** - CI will automatically run tests

## CI/CD

GitHub Actions workflows:
- **CI Pipeline** (`ci.yml`): Runs on every PR
  - Backend: lint, type-check, tests
  - Frontend: lint, type-check, tests

- **Deployment** (`deploy.yml`): Deploys to Azure VM on merge to main (Phase 12)

## Environment Variables

See `.env.example` for all available configuration options.

**Key variables:**
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `TFL_API_KEY` - TfL API key (required in Phase 5)
- `AUTH0_DOMAIN` - Auth0 tenant domain (required in Phase 3)
- `AUTH0_API_AUDIENCE` - Auth0 API identifier (required in Phase 3)
- `AUTH0_ALGORITHMS` - JWT signing algorithms (default: RS256)

## Auth0 Setup

Authentication is handled by Auth0. For detailed setup instructions, see [docs/auth0-setup.md](./docs/auth0-setup.md).

**Quick start:**

1. Create a free Auth0 account at https://auth0.com
2. Create an API in the Auth0 dashboard with identifier `https://api.isthetube.com` (or your domain)
3. Create a Single Page Application for the frontend
4. Configure callback URLs and CORS settings
5. Add Auth0 credentials to `backend/.env`:
   ```bash
   AUTH0_DOMAIN=your-tenant.auth0.com
   AUTH0_API_AUDIENCE=https://api.isthetube.com
   AUTH0_ALGORITHMS=RS256
   ```

**Local development:**
The backend supports mock JWT mode for development without Auth0. When `DEBUG=True`, the application accepts locally generated mock JWTs, eliminating the need for Auth0 during local testing. See [docs/auth0-setup.md](./docs/auth0-setup.md) for details.

**API Endpoints:**
- `GET /api/v1/auth/me` - Get current authenticated user (auto-creates user on first login)

## Admin Endpoints

Certain endpoints require admin privileges for system management and monitoring. Admin status is tracked in the `admin_users` table and checked via the `require_admin()` dependency.

### Granting Admin Access

Admin users must be manually created in the database. To grant admin privileges to a user:

```sql
-- Get the user's ID
SELECT id FROM users WHERE external_id = 'auth0|your_user_id';

-- Grant admin role
INSERT INTO admin_users (user_id, role, granted_at)
VALUES ('user-uuid-here', 'admin', NOW());
```

**Note:** Production deployments should implement a secure admin management interface. Manual database access is acceptable for the MVP (Phase 8).

### Available Admin Endpoints

#### Alert Management

**POST /api/v1/admin/alerts/trigger-check**
- Manually trigger an immediate disruption check for all active routes
- Bypasses normal Celery schedule
- Returns statistics: routes_checked, alerts_sent, errors
- Use case: Testing or forcing update after known TfL issues

**GET /api/v1/admin/alerts/worker-status**
- Check Celery worker health and status
- Returns: worker_available, active_tasks, scheduled_tasks, last_heartbeat
- Use case: Monitoring worker health, debugging task issues

**GET /api/v1/admin/alerts/recent-logs**
- Query recent notification logs with pagination
- Query params: `limit` (1-1000, default 50), `offset` (default 0), `status` (sent/failed/pending)
- Returns paginated list of notification logs
- Use case: Audit trail, debugging failed notifications

#### TfL Data Management

**POST /api/v1/admin/tfl/build-graph**
- Build station connection graph from TfL API data
- Required for route validation
- Returns: lines_count, stations_count, connections_count
- Use case: Initial setup or refreshing station data

### Example Usage

```bash
# Get auth token (use Auth0 or mock JWT in dev)
TOKEN="your-jwt-token"

# Trigger manual alert check
curl -X POST https://api.isthetube.com/api/v1/admin/alerts/trigger-check \
  -H "Authorization: Bearer $TOKEN"

# Check worker status
curl -X GET https://api.isthetube.com/api/v1/admin/alerts/worker-status \
  -H "Authorization: Bearer $TOKEN"

# Get recent failed notifications
curl -X GET "https://api.isthetube.com/api/v1/admin/alerts/recent-logs?status=failed&limit=20" \
  -H "Authorization: Bearer $TOKEN"
```

### Authorization

All admin endpoints return:
- **401 Unauthorized** - Missing or invalid JWT token
- **403 Forbidden** - Valid JWT but user is not an admin

## Secret Management with python-dotenv-vault

This project uses **python-dotenv-vault** for encrypted secret management across environments.

### Local Development

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Fill in your local values** in `.env`

3. **Run the app** - `load_dotenv()` automatically loads `.env`

### Managing Encrypted Secrets

Environment-specific configuration files (`.env.ci`, `.env.production`) are encrypted into `.env.vault` for secure storage in version control.

**Building .env.vault:**
```bash
# After editing .env.ci or .env.production
npx dotenv-vault@latest build

# Alternatively, pre-commit hooks automatically rebuild .env.vault when .env.* files change
```

**Viewing decryption keys:**
```bash
npx dotenv-vault@latest keys
```

This displays the `DOTENV_KEY_CI` and `DOTENV_KEY_PRODUCTION` values needed for decryption.

### CI/CD Configuration

**GitHub Actions:**
1. Run `npx dotenv-vault@latest keys` to get the CI decryption key
2. Go to GitHub repo → Settings → Secrets and variables → Actions
3. Add secret: `DOTENV_KEY_CI` with the full key string from `.env.keys`
4. CI workflow automatically decrypts `.env.vault` using this key

**Production Deployment:**
1. Set `DOTENV_KEY_PRODUCTION` as an environment variable on your production server
2. The application automatically decrypts `.env.vault` at startup

### How It Works

1. **Config Loading** (`backend/app/core/config.py`):
   - `load_dotenv()` is called BEFORE any configuration is read
   - Local: loads plain `.env` file
   - CI/Production: decrypts `.env.vault` using `DOTENV_KEY` environment variable

2. **Pre-commit Hooks**:
   - Automatically rebuild `.env.vault` when `.env.ci` or `.env.production` changes
   - Ensures encrypted vault is always up-to-date

3. **Security**:
   - `.env`, `.env.ci`, `.env.production` - gitignored (never committed)
   - `.env.vault` - encrypted, safe to commit
   - `.env.keys` - gitignored, store in password manager (DO NOT COMMIT)

### Updating Secrets

1. Edit `.env.ci` or `.env.production`
2. Run `npx dotenv-vault@latest build` (or let pre-commit do it)
3. Commit the updated `.env.vault`
4. Update GitHub Secrets if decryption keys changed

## Contributing

1. Follow the existing code style
2. Write tests for new features
3. Update documentation as needed
4. Ensure all tests pass before submitting PR
5. Keep commits atomic and well-described

## License

MIT License - see [LICENSE](./LICENSE) file for details.

## Roadmap

See [implementation_plan.md](./implementation_plan.md) for detailed implementation phases.

**Completed:**
- ✅ Phase 1: Project Foundation
- ✅ Phase 2: Database Models & Migrations
- ✅ Phase 3: Auth0 Integration
- ✅ Phase 4: Contact Verification
- ✅ Phase 5: TfL Data Integration
- ✅ Phase 6: Route Management
- ✅ Phase 7: Notification Preferences
- ✅ Phase 8: Alert Processing Worker

**Upcoming:**
- Phase 9: Admin Dashboard Backend
- Phase 10: Frontend Development
- Phase 11: Testing & Quality
- Phase 12: Deployment

## Support

For issues or questions, please open a GitHub issue.
