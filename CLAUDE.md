# FundPilot

## Coding Standards & Development Guidelines

### General Principles

- Prioritize readability over cleverness
- Keep functions small and focused
- Avoid deeply nested logic
- Prefer explicit code over magic behavior
- Write maintainable production-grade code
- Avoid premature optimization
- Follow clean architecture principles

---

### Python Version

Python **3.12.13** only.

Root directory must contain `.python-version` with content `3.12.13`. Docker base image must use `python:3.12.13-slim`.

---

### Style Rules

- PEP8 + PEP257
- Full type hints on all public functions
- Max line length: 88 characters
- Variables/functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_CASE`
- Files: `snake_case.py`

---

### Import Order

1. Python standard library
2. Third-party libraries
3. Local modules

No wildcard imports (`from module import *`).

---

### Project Structure

```
app/
├── api/              # API routes (thin, no business logic)
├── core/             # Config, base classes, constants
├── services/         # Business logic only
├── repositories/     # Database access only
├── models/           # SQLAlchemy ORM models
├── schemas/          # Pydantic request/response schemas
├── integrations/     # Third-party APIs (AkShare, news, etc.)
├── ai/               # AI analysis adapters
├── tasks/            # APScheduler scheduled tasks
├── utils/            # Utility functions
└── tests/            # Tests
```

Rules:
- Business logic must NOT exist inside API routes
- Database access must be isolated in repositories
- AI logic must be isolated inside `ai/`
- Third-party API calls must be isolated inside `integrations/`

---

### API Response Format

Success:
```json
{
  "success": true,
  "data": {},
  "message": ""
}
```

Error:
```json
{
  "success": false,
  "error": {
    "code": "INVALID_ARGUMENT",
    "message": "Invalid sector code"
  }
}
```

---

### Database Standards

- SQLAlchemy 2.0 async style
- Table names: plural snake_case (`funds`, `sector_snapshots`, `news_articles`)
- All tables must include `created_at` + `updated_at`
- Prefer UUID primary keys
- Store AI outputs as structured JSON (never raw natural-language text only)

### Service Layer

Business logic belongs ONLY in `services/`. Not in API routes, repositories, or models.

### Repository Layer

Repositories ONLY query/insert/update/delete. They must NOT contain business logic or AI analysis.

### AI Module

All AI logic lives in `app/ai/`. Provider-specific logic uses adapters:

```python
class AIProvider(ABC):
    async def analyze(self, prompt: str) -> dict: ...
```

---

### Logging & Error Handling

- Use `logging`, never `print()`
- Never silently swallow exceptions — always log and re-raise
- Google-style docstrings only when intent is non-obvious

### Testing

- `pytest` + `pytest-asyncio`
- Focus on services, business logic, AI parsing, repositories

### Scheduler

- APScheduler
- All tasks support manual triggering + configurable intervals
- All jobs must support retries, logging, and deduplication

### Git

Branch naming: `feature/`, `fix/`, `refactor/`

Commit format: `feat:` / `fix:` / `refactor:`
