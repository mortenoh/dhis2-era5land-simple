FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    git \
    g++ \
    libgeos-dev \
    libproj-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY main.py ./

# Install dependencies
RUN uv sync --frozen --no-dev || uv sync --no-dev


FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install runtime dependencies and cron
RUN apt-get update && apt-get install -y \
    libgeos-c1v5 \
    libproj25 \
    libexpat1 \
    cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy from builder
COPY --from=builder /app /app

# Copy entrypoint
COPY scripts/scheduler.sh /scheduler.sh
RUN chmod +x /scheduler.sh

# Default: run the import
CMD ["/usr/local/bin/uv", "run", "--no-sync", "python", "main.py"]
