# IsTheTubeRunning

A TfL (Transport for London) disruption alert system that notifies users of service interruptions on their regular routes.

## Project Status

**Phase 1: Project Foundation** ✅ Complete

See [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) for the full roadmap.

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

### API Documentation
- `http://localhost:8000/docs` - Swagger UI
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
- `AUTH0_DOMAIN` - Auth0 configuration (required in Phase 3)

## Contributing

1. Follow the existing code style
2. Write tests for new features
3. Update documentation as needed
4. Ensure all tests pass before submitting PR
5. Keep commits atomic and well-described

## License

MIT License - see [LICENSE](./LICENSE) file for details.

## Roadmap

See [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) for detailed implementation phases.

**Completed:**
- ✅ Phase 1: Project Foundation

**Upcoming:**
- Phase 2: Database Models & Migrations
- Phase 3: Auth0 Integration
- Phase 4: Contact Verification
- Phase 5: TfL Data Integration
- Phase 6: Route Management
- Phase 7: Notification Preferences
- Phase 8: Alert Processing Worker
- Phase 9: Admin Dashboard Backend
- Phase 10: Frontend Development
- Phase 11: Testing & Quality
- Phase 12: Deployment

## Support

For issues or questions, please open a GitHub issue.
