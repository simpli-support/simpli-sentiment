# Improvement Opportunities

Analysis of the simpli-sentiment codebase with implementation status.

---

## Implemented

### Keyword-based Sentiment Analysis (was: Stub Implementations)
- **`POST /analyze`** — implemented keyword-based sentiment scoring with 50+ positive/negative keywords, escalation trigger detection, and automatic alert generation when risk >= 0.5
- **`GET /customers/{customer_id}/sentiment`** — now returns real sentiment timeline from in-memory store with trend calculation (improving/declining/stable)
- **`GET /alerts`** — returns alerts auto-generated from high-risk analyses, with filtering by severity and customer_id

### Input Validation
- `customer_id` validated with regex pattern `^[A-Za-z0-9][A-Za-z0-9\-_]{0,63}$`
- `text` field constrained to 1–10,000 characters
- `channel` field limited to 64 characters
- All validated via Pydantic `Field()` constraints

### Dependencies Reorganized
- Moved 8 unused heavy dependencies (`torch`, `transformers`, `spacy`, `sqlalchemy`, `alembic`, `redis`, `httpx`) to optional dependency groups (`ml`, `db`, `cache`, `all`)
- Added `pydantic-settings` as core dependency
- Added `pytest-cov` to dev dependencies
- Core install reduced from ~4 GB to ~50 MB

### Test Coverage: 2 tests -> 36 tests (99% coverage)
- All endpoints tested including error cases and edge cases
- Input validation tests (missing fields, empty text, invalid customer_id, oversized text, invalid JSON)
- Pagination tests for both `/customers/{id}/sentiment` and `/alerts`
- Alert generation and filtering tests
- Internal function unit tests (`_analyze_text`, `_score_to_label`, `_escalation_risk`)
- CLI tests (`version`, `serve --help`)

### Environment Configuration
- Created `settings.py` with `pydantic_settings.BaseSettings` loading from env vars and `.env` files
- `APP_ENV`, `APP_HOST`, `APP_PORT`, `LOG_LEVEL`, `WORKERS`, `DATABASE_URL`, `REDIS_URL` all configurable
- CLI defaults now sourced from settings module

### Dockerfile Hardened
- Pinned Python to `3.12.8-slim`
- Multi-stage build (builder + runtime) to reduce image size
- Runs as non-root `appuser`
- Added `HEALTHCHECK` directive
- Uses stdlib `urllib.request` instead of requiring curl

### Logging and Observability
- Integrated `structlog` for structured logging
- Request/response logging middleware with correlation IDs (`X-Request-ID` header)
- Escalation alerts logged with `logger.warning`

### CORS Middleware
- Added `CORSMiddleware` for frontend consumption

### Pagination and Filtering
- `GET /customers/{id}/sentiment` supports `limit` (1-500) and `offset` query params
- `GET /alerts` supports `severity`, `customer_id`, `limit`, and `offset` filtering

### CLI Improvements
- Added `--workers` flag for production deployment
- Added `--log-level` flag
- All defaults loaded from environment/settings

### OpenAPI Improvements
- Added `tags` to all routes (`customers`, `analysis`, `alerts`, `system`)
- Added `responses` with error models for documented error codes
- Added `ErrorResponse` model for consistent error formatting

### CI/CD Improvements
- Added `pytest-cov` for coverage reporting
- Test job now runs with `--cov` and `--cov-report`
- Coverage XML uploaded as artifact for CI integration

### .gitignore Updates
- Added IDE directories (`.vscode/`, `.idea/`)
- Added editor temp files (`*.swp`, `*.swo`, `*~`)
- Added macOS `.DS_Store`

### Exception Handling
- Added `ValueError` exception handler returning JSON 400 responses
- Customer ID format validation on GET endpoint returns proper 400

---

## Remaining (Not Yet Implemented)

### Authentication and Rate Limiting
- No auth mechanism (API key, JWT, OAuth)
- No rate limiting middleware
- **Recommendation:** Add API key auth via FastAPI `Depends()` and `slowapi` for rate limiting

### Database Persistence
- Sentiment history stored in-memory (lost on restart)
- **Recommendation:** Integrate SQLAlchemy (available as `pip install simpli-sentiment[db]`) with migrations via Alembic

### ML-based Sentiment Analysis
- Current implementation uses keyword matching (adequate for basic use)
- **Recommendation:** Integrate HuggingFace transformers (available as `pip install simpli-sentiment[ml]`) for production-grade analysis

### Redis Caching
- No caching layer for repeated queries
- **Recommendation:** Integrate Redis (available as `pip install simpli-sentiment[cache]`) for response caching
