# Dockerfile for User Registration API
# Decision: Using Alpine Linux for smaller images

FROM python:3.11-alpine

WORKDIR /app

# Install build and runtime dependencies
# Decision: asyncpg and bcrypt need compilation dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    cargo \
    linux-headers

# Install poetry
RUN pip install --no-cache-dir poetry==1.8.3

# Configure poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# Copy dependency files (for Docker layer caching)
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --no-root && rm -rf $POETRY_CACHE_DIR

# Copy application code
COPY gunicorn_conf.py ./
COPY src/ ./src/
COPY config/ ./config/
COPY tests/ ./tests/
COPY .env.example .env

# Add virtualenv to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose port
EXPOSE 8000

# Default command (overridden in docker-compose for production with Gunicorn)
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
