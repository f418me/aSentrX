# Stage 1: Build stage (optional, but good for potentially complex builds later)
FROM python:3.12-slim AS builder

# Install git for fetching git-based dependencies
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt ./
# Temp fix for bitfinex
RUN pip install requests

RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Final stage
FROM python:3.12-slim AS final

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

COPY main.py .
COPY utils/ ./utils/
COPY ai/ ./ai/
COPY experiments/ ./experiments/
COPY socialmedia/ ./socialmedia/
COPY utils/ ./utils/


# Create a non-root user and switch to it
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid 1001 --shell /bin/bash --create-home appuser
RUN chown -R appuser:appuser /app

USER appuser

# Command to run the application
CMD ["python", "main.py"]