# User Registration API

Production-ready user registration with email verification, built with Clean Architecture.

📚 [Architecture Documentation](docs/architecture.md)

---

## Quick Start

**Prerequisites:** Docker + Docker Compose

```bash
cp .env.example .env #copy default environment variables
make install  # Build and start all services
```

**Access:**

- API: <http://localhost:8000>
- API Docs: <http://localhost:8000/docs>
- Health Check: <http://localhost:8000/api/v1/health>
- Metrics: <http://localhost:8000/api/v1/metrics>
- Mailhog (emails): <http://localhost:8025>

---

## Testing the API

Register a user:

```bash
curl -X POST http://localhost:8000/api/v1/users/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "SecurePass123"}'
```

Check email at <http://localhost:8025> for the 4-digit activation code, then activate:

```bash
curl -X POST http://localhost:8000/api/v1/users/activate \
  -H "Content-Type: application/json" \
  -H "Authorization: Basic $(echo -n 'test@example.com:SecurePass123' | base64)" \
  -d '{"activation_code": "1234"}'
```

Don't forget to replace `1234` in the payload using the actual code sent by email.

See interactive docs at <http://localhost:8000/docs> for more and observability metrics at <http://localhost:8000/api/v1/metrics>

---

## Running Tests

```bash
make test      # Unit + integration (fast, ~10s)
make test-e2e  # Full system with Celery (~30s)
make quality   # Ruff + mypy + pre-commit
```

**Coverage:** ~73% unit/integration (pytest-cov), comprehensive E2E coverage (Behave)

**Why not 100%?** Pragmatic Testing Strategy :

- **Business logic (Domain/Application):** 96-100% coverage - Critical paths fully tested
- **API layer (Presentation):** 71-93% coverage - Contracts and error handling
- **Infrastructure (Celery/SMTP):** 0% in unit tests, 100% in E2E tests with real services
- **rate limiting & observability:** 0%. TO BE ADDED.

Infrastructure code is tested with real Celery workers and Mailhog SMTP in E2E tests rather than mocked in unit tests. This provides higher confidence in production behavior without the overhead of maintaining extensive mocks for third-party services.

---

## Technical Choices

- **Clean Architecture** - Domain logic independent of frameworks, testable and scalable
- **FastAPI + asyncpg** - Async performance, fast API responses, automatic OpenAPI docs
- **Gunicorn + Uvicorn workers** - Production ASGI deployment with zero-downtime reloads and worker health monitoring
- **Raw SQL (no ORM)** - Full control, demonstrates SQL proficiency per requirements
- **Celery + Redis** - Background email processing keeps API fast, workers scale independently

**Stack:** Python 3.11, FastAPI, PostgreSQL, asyncpg, Redis, Celery, Gunicorn, Uvicorn, Docker, pytest, Behave

---

## Observability & Rate Limiting

### Observability

The API includes production-grade observability middleware with **Redis-backed metrics storage** that works across multiple Gunicorn workers:

**Health Check Endpoint:**

```bash
curl http://localhost:8000/api/v1/health
```

Returns service status and database connectivity:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "checks": {
    "database": "healthy"
  }
}
```

**Metrics Endpoint:**

```bash
curl http://localhost:8000/api/v1/metrics
```

Returns request metrics, latency percentiles (p50, p95, p99), and business metrics:

```json
{
  "request_counts": {"GET /api/v1/health": 42, ...},
  "status_counts": {200: 40, 404: 2},
  "error_count": 2,
  "business_metrics": {
    "registrations": 15,
    "activations": 12
  },
  "latencies": {
    "POST /api/v1/users/register": {
      "count": 15,
      "p50": 145.2,
      "p95": 187.5,
      "p99": 195.8,
      "min": 120.1,
      "max": 198.3
    }
  }
}
```

All metrics are logged as structured JSON for easy ingestion by log aggregators (ELK, Splunk, Datadog).

**Multi-Worker Support:**

- Metrics stored in **Redis** for aggregation across all Gunicorn workers
- Consistent view of system metrics regardless of which worker handles the request
- Survives individual worker restarts
- Production-ready for horizontally scaled deployments

**Disable metrics** (for testing or performance):

```bash
ENABLE_METRICS=false docker-compose up
```

### Rate Limiting

Production-grade rate limiting using Redis sliding window algorithm protects against abuse and DDoS:

**Rate Limits:**

- **Registration:** 5 requests per hour per IP address
- **Activation:** 3 attempts per minute per email
- **Global:** 1000 requests per minute per endpoint

**Rate limit headers** are included in all responses:

```
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 2
X-RateLimit-Reset: 1699123456
```

When rate limit is exceeded, API returns **429 Too Many Requests** with retry information:

```json
{
  "error": "RateLimitExceeded",
  "message": "Too many registration attempts. You can register up to 5 accounts per hour.",
  "retry_after_seconds": 3540
}
```

**Disable rate limiting** (for testing):

```bash
ENABLE_RATE_LIMITING=false docker-compose up
```

**Configure limits** via environment variables:

```bash
RATE_LIMIT_REGISTRATION_PER_HOUR=10
RATE_LIMIT_ACTIVATION_PER_MINUTE=5
RATE_LIMIT_GLOBAL_PER_MINUTE=2000
```

**Technical Details:**

- Uses **Redis ZSET** for distributed sliding window rate limiting
- Works across multiple API instances (stateless, shared Redis)
- Automatic cleanup of expired entries
- Fails open on Redis errors to avoid service disruption

---

## Implementation Summary

This project fully implements the technical requirements using **Clean Architecture** to separate business logic from frameworks. We chose **FastAPI** for async performance with automatic API documentation, **PostgreSQL with raw SQL** (no ORM) to demonstrate SQL proficiency and control, **asyncpg** for faster database operations, and **Celery + Redis** for background email processing to keep API responses fast. The codebase includes **comprehensive test coverage** across three testing tiers (unit, integration, E2E with Behave) and production-grade tooling (Ruff, mypy, pre-commit hooks).

**Production readiness:** The system is containerized and stateless, enabling trivial horizontal scaling. The API includes observability (metrics, health checks, structured logging) and rate limiting (Redis sliding window). To deploy to production, you would additionally need: (1) database migration system (Alembic instead of schema recreation), (2) secrets management (AWS Secrets Manager, Vault), (3) enhanced observability (APM like Datadog, distributed tracing with OpenTelemetry), (4) HTTPS/TLS enforcement, and (5) CI/CD pipeline with rolling deployments.

**Scaling:** The stateless API scales horizontally by adding containers behind a load balancer. Celery workers scale independently based on email queue depth. Database scales with read replicas (async replication for high-read workloads) or connection pooling (PgBouncer).

---

## Deployment

Build and run anywhere (Kubernetes, ECS, Cloud Run):

```bash
docker build -t user-registration-api .
docker run -p 8000:8000 \
  -e DATABASE_HOST=your-db \
  -e REDIS_HOST=your-redis \
  user-registration-api
```

**Production requirements:** PostgreSQL 15+, Redis, SMTP server

**ASGI Server:** The application uses **Gunicorn + Uvicorn workers** for production deployment:

- **Gunicorn** manages multiple worker processes (process-level parallelism)
- **Uvicorn workers** handle async requests (ASGI-compatible, full async/await support)
- **Zero-downtime deployments** via graceful reloads (SIGHUP signal)
- **Worker health monitoring** with automatic restart on failure
- Configuration in `gunicorn_conf.py` (workers: 2x CPU + 1, graceful timeout: 30s)

This is the industry-standard production pattern for FastAPI, combining Gunicorn's mature process management with Uvicorn's async performance.

---

## Project Structure

```
user-registration-api/
├── src/
│   ├── domain/                     # Business logic (entities, ports)
│   ├── application/                # Use cases
│   ├── infrastructure/             # Adapters
│   │   ├── database/               # PostgreSQL (asyncpg, raw SQL)
│   │   ├── email/                  # SMTP email service
│   │   ├── tasks/                  # Celery task queue
│   │   ├── observability/          # Metrics middleware
│   │   └── rate_limiting/          # Redis rate limiter
│   └── presentation/               # HTTP API (FastAPI routes)
├── tests/
│   ├── unit/                       # Fast, isolated tests
│   ├── integration/                # API + database tests
│   └── e2e/                        # Full system (Behave BDD)
├── docs/architecture.md            # Clean Architecture diagram
└── docker-compose.yml              # All services
```

---

## Quality of code and developer experience matter

The choices :

- Stengthening the codebase using mypy, ruff & pre-commit ensuring consistency in both code format & type checking avoiding mistakes at the commit level.
- Abstraction : each layer has a responsability. We stick to SOLID principles making it easier to test & debug.
- We test three level from the ground up. Any new feature should come with it's related tests.
- Production-First Development: The provided docker-compose.yml is production-ready, ensuring the developer environment accurately mirrors the deployment target. Hot-reloading for development is enabled via overrides/volumes for enhanced developer experience.

---

## Essential Commands

```bash
make install   # First-time setup
make up        # Start services
make test      # Run fast tests
make test-e2e  # Run E2E tests
make diagrams  # Generate architecture diagrams
make quality   # Code quality checks
make logs      # View all logs
```

Run `make help` for all commands.

---

## Future Work & Production Backlog

Given the time constraint, a pragmatic trade-off was made to prioritize functional completeness and core architecture over 100% test coverage for all newly implemented features. The following are immediately prioritized for production readiness:
Because of this is intended to be a test, I'd rather focusing on the features than the tests. Therefore, despite wanted to add tests to these. There is currently none.

- Observability & Rate limiting unit tests
- Observability & Rate limiting integration tests
- Observability & Rate limiting E2E tests
- Integrate a proper observability service (datadog, grafana..)

## Project Authorship and Development Notes

The core architecture, technical choices, and complex logic were developed entirely by me. I leveraged modern AI tooling (e.g., Claude Code) for ancillary tasks like structured documentation, docstring generation, and basic boilerplate/edge-case unit test scaffolding, allowing maximum focus on high-value architectural components.

**Built for Dailymotion Staff Engineer position**
