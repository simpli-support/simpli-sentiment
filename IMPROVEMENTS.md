# Improvement Opportunities

Comprehensive analysis of the simpli-sentiment codebase identifying areas for improvement.

---

## Critical: Stub Implementations

All three core endpoints return hardcoded data with no actual logic.

### `POST /analyze` (`src/simpli_sentiment/app.py:59-67`)
- Always returns `score=0.0`, `label="neutral"`, `escalation_risk=0.0`
- `customer_id` and `text` from the request are never used
- No sentiment analysis, escalation risk calculation, or trigger detection
- **Fix:** Integrate `transformers` (already declared as a dependency) to perform real sentiment analysis, compute escalation risk from score trends, and extract frustration triggers from text

### `GET /customers/{customer_id}/sentiment` (`src/simpli_sentiment/app.py:48-56`)
- Returns empty timeline with `current_score=0.0` for every customer
- No database lookup or data persistence
- **Fix:** Connect to a database via SQLAlchemy (already declared) to store and retrieve sentiment history per customer

### `GET /alerts` (`src/simpli_sentiment/app.py:70-73`)
- Always returns an empty list
- No alert generation or filtering logic
- **Fix:** Implement alert generation based on escalation risk thresholds and sentiment trend analysis

---

## Critical: Missing Input Validation

### No `customer_id` validation (`app.py:48-49`)
- Accepts any string, including empty strings
- No format enforcement (e.g., `C-XXXX` pattern)
- Potential for injection or enumeration attacks
- **Fix:** Add a regex-validated `customer_id` field using Pydantic's `Field(pattern=...)`

### No `text` field constraints (`app.py:13-15`)
- No minimum or maximum length on `text`
- Empty strings accepted silently
- Extremely large payloads could cause DoS
- **Fix:** Add `Field(min_length=1, max_length=10000)` to the `AnalyzeRequest` model

---

## High: Unused Dependencies (8 of 13)

**File:** `pyproject.toml:10-24`

Only 4 of 13 production dependencies are actually imported anywhere in the code:

| Dependency | Size Impact | Status |
|---|---|---|
| `torch>=2.5` | ~3 GB | **Unused** |
| `transformers>=4.46` | ~500 MB | **Unused** |
| `spacy>=3.8` | ~400 MB | **Unused** |
| `sqlalchemy>=2.0` | ~15 MB | **Unused** |
| `alembic>=1.14` | ~5 MB | **Unused** |
| `redis>=5.2` | ~5 MB | **Unused** |
| `structlog>=24.4` | ~2 MB | **Unused** |
| `python-dotenv>=1.0` | ~1 MB | **Unused** |
| `httpx>=0.28` | ~5 MB | **Unused** |

**Impact:** ~4 GB of unnecessary install weight; increased attack surface; misleading about actual functionality.

**Fix:** Move unused dependencies to `[project.optional-dependencies]` groups (e.g., `ml`, `db`, `cache`) and only promote them to core dependencies as features are implemented.

---

## High: Test Coverage (~25%)

**File:** `tests/test_app.py`

Only 2 tests exist, covering the happy path of `/health` and `/analyze`.

### Missing test cases:
- `GET /customers/{customer_id}/sentiment` - not tested at all
- `GET /alerts` - not tested at all
- `POST /analyze` with missing required fields (`customer_id`, `text`)
- `POST /analyze` with empty `text`
- `POST /analyze` with `channel` parameter
- Response schema validation (all fields present and correct types)
- Invalid JSON body handling
- CLI (`cli.py`) is entirely untested

**Fix:** Add tests for all endpoints including error cases, and add CLI tests using Typer's `CliRunner`.

---

## High: No Authentication or Rate Limiting

- All endpoints are publicly accessible with no auth
- No API key validation or JWT/OAuth support
- No rate limiting - vulnerable to abuse
- **Fix:** Add FastAPI dependency injection for API key or token-based auth; add rate limiting middleware (e.g., `slowapi`)

---

## Medium: Environment Configuration Not Integrated

### `.env.example` declares vars that are never loaded
- `APP_ENV`, `APP_HOST`, `APP_PORT` defined but unused
- `DATABASE_URL`, `REDIS_URL` commented out but never referenced
- `python-dotenv` is a declared dependency but never imported

### `cli.py:11-13` uses hardcoded defaults
- Host and port are hardcoded as `0.0.0.0` and `8000`
- No log level or worker count configuration

**Fix:** Create a settings module using Pydantic's `BaseSettings` (built into `pydantic-settings`) to load from environment variables and `.env` files.

---

## Medium: Dockerfile Issues

**File:** `Dockerfile`

| Issue | Line | Fix |
|---|---|---|
| Unpinned Python version (`3.12-slim`) | 1 | Pin to exact version (e.g., `3.12.8-slim`) |
| Runs as root | - | Add `RUN useradd -r app` and `USER app` |
| No `HEALTHCHECK` | - | Add `HEALTHCHECK CMD curl -f http://localhost:8000/health` |
| No multi-stage build | - | Use builder stage to reduce final image size |
| Hardcoded uvicorn args | 7 | Use env vars or the CLI entrypoint |

---

## Medium: No Logging or Observability

- `structlog` is declared as a dependency but never imported or configured
- No request logging, error logging, or access logs
- No performance metrics or correlation IDs
- Debugging production issues would be impossible

**Fix:** Configure structlog with JSON output, add request/response logging middleware, and add correlation ID injection.

---

## Medium: No Pagination or Filtering

### `GET /customers/{customer_id}/sentiment` (`app.py:48-56`)
- Returns unbounded `timeline` list - will grow without limit
- No date range filtering
- No pagination parameters (`limit`, `offset`)

### `GET /alerts` (`app.py:70-73`)
- Returns all alerts with no filtering by severity, customer, or date
- No pagination

**Fix:** Add `limit`, `offset`, and date range query parameters to both endpoints.

---

## Low: CLI Improvements

**File:** `src/simpli_sentiment/cli.py`

- No `--workers` flag for production deployment (uvicorn defaults to 1)
- No `--log-level` flag
- `version` command imports lazily but could use `importlib.metadata` for consistency

---

## Summary by Priority

| Priority | Count | Categories |
|---|---|---|
| **Critical** | 5 | Stub endpoints (3), input validation (2) |
| **High** | 3 | Unused deps, test coverage, auth/rate limiting |
| **Medium** | 4 | Env config, Dockerfile, logging, pagination |
| **Low** | 1 | CLI enhancements |
