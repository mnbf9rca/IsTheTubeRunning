# Architecture Decision Records (ADR)

This document captures key architectural decisions made during the development of the TfL Disruption Alert System.

**Note**: When running commands in `/backend`, ALWAYS use `uv run` (never naked `python`). Do not use `pip`.

**ensure that you read any specific ADRs related to development setup and tools for more context.**

---

## ADR Categories

Architecture decisions are organized into the following categories:

### [01. Infrastructure](./01-infrastructure.md)
Project structure, deployment, and infrastructure decisions.
- Monorepo Structure
- Azure VM + Docker Compose Deployment
- Cloudflare + UFW Firewall

### [02. Development Tools & Code Quality](./02-development-tools.md)
Tools and frameworks for development.
- uv for Python Package Management
- Tailwind CSS v4
- shadcn/ui Component Library

### [03. Database & Data Modeling](./03-database.md)
Database design and data modeling decisions.
- UUIDs for Primary Keys
- Soft Deletes
- JSON for Route Schedules
- Explicit Route Timezones

### [04. Authentication & Authorization](./04-authentication.md)
Authentication and authorization architecture.
- Auth0 for Identity Provider
- Backend Auth as Single Source of Truth
- Admin Role-Based Authorization
- Backend Availability First Pattern
- Explicit Backend Validation in Callback
- Intent Preservation on Auth Redirect

### [05. Security & Secrets Management](./05-security.md)
Security and secrets management decisions.
- python-dotenv-vault for Secrets
- DB Credential Separation
- Required Config Validation
- Rate Limiting Strategy
- Frontend Configuration in JSON

### [06. Contact Verification & User Management](./06-user-management.md)
User management and contact verification.
- Code-based Verification
- Simple Verification Codes
- Separate Verification Flow
- Privacy-Focused User Deletion
- Explicit NotificationPreference Deletion on Anonymization

### [07. External API Integration](./07-external-apis.md)
Integration with external APIs.
- pydantic-tfl-api Integration
- Dynamic Cache TTL
- Simplified Station Graph
- Admin Endpoint for Graph Building
- Multi-line Routes

### [08. Background Jobs & Workers](./08-background-jobs.md)
Background job processing and workers.
- Celery + Redis
- Content-Based Alert Deduplication
- Hybrid Task Scheduling
- Worker Database Sessions

### [09. API Design](./09-api-design.md)
API design patterns and approaches.
- KISS Analytics Approach

### [10. Testing Strategy](./10-testing.md)
Testing approaches and patterns.
- Comprehensive Test Coverage Philosophy
- Test Database Setup
- Test Authentication Pattern
- NullPool for Async Test Isolation
- Async Test Mocking Strategy
- Test Database Dependency Override Pattern
- IntegrityError Recovery Test Pattern

### [11. Frontend State Management](./11-frontend-state-management.md)
Frontend state management patterns for complex components.
- Complex State Management Pattern
- Pure Function Architecture
- When to Apply This Pattern
- Implementation Guidelines
- Testing Requirements

### [12. Observability & Distributed Tracing](./12-observability.md)
Observability and distributed tracing decisions.
- OpenTelemetry for Distributed Tracing

---

## How to Add New Architecture Decisions

When making a significant architectural decision, add it to this collection using the following process:

1. **Choose the correct file** - Add your decision to the most appropriate category file above, or create a new category file if needed (update this README accordingly).

2. **Use the ADR template** - Format your decision as follows:

```markdown
## [Decision Title]

### Status
[Active | Deprecated | Superseded by [Decision Title]]

### Context
[What is the issue that we're seeing that is motivating this decision or change?]

### Decision
[What is the change that we're proposing and/or doing?]

### Consequences
**Easier:**
- [What becomes easier because of this decision?]
- [List multiple benefits]

**More Difficult:**
- [What becomes more difficult because of this decision?]
- [List tradeoffs and limitations]
```

3. **Be specific** - Include concrete examples, code patterns, or file references where relevant.

4. **Consider both sides** - Always document both benefits (easier) and tradeoffs (more difficult). Every architectural decision has tradeoffs.

5. **Update status when superseded** - If a decision is replaced by a newer one, update its status to "Superseded by [New Decision Title]" rather than deleting it. This preserves historical context.

6. **Keep it concise** - ADRs should be scannable. Link to external docs for detailed implementation guides if needed.

7. **Review before merging** - Architectural decisions affect the entire team and future maintainers. Get review before merging significant changes to this document.

8. **Update this index** - If you create a new category file, add it to the list above with a brief description.
