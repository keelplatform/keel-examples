FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for layer caching.
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache .

# Copy source.
COPY src ./src
RUN uv pip install --system --no-cache -e .

# Default command — run the multi-round agent workload.
CMD ["python", "-m", "keel_research_agent.run"]
