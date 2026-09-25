# Stage 1: Build production frontend assets
FROM node:20-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python ASGI container
FROM python:3.13-slim
WORKDIR /app

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install backend dependencies
COPY backend/pyproject.toml ./pyproject.toml
RUN pip install --no-cache-dir .

# Copy application source
COPY backend/app ./app
COPY run.py ./run.py
COPY worker.py ./worker.py

# Copy compiled frontend assets from Stage 1
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

