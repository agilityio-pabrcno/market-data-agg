FROM python:3.13-slim

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Poetry
ENV POETRY_VERSION=2.1.3
RUN pip install poetry==${POETRY_VERSION}

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Configure Poetry to not create virtual env (we're in Docker)
ENV POETRY_VIRTUALENVS_CREATE=false

# Install dependencies (without dev); skip project so README.md not required
RUN poetry install --only main --no-interaction --no-ansi --no-root

# Copy application code
COPY . .

# App package lives under src/
ENV PYTHONPATH=/app/src

# Run the application
CMD ["uvicorn", "market_data_agg.main:app", "--host", "0.0.0.0", "--port", "8000"]
