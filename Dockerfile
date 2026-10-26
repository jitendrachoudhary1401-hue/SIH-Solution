# Stage 1: Build Frontend Assets
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend & Worker Environment
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_PATH=/app/.runtime/models \
    STORAGE_PATH=/app/.runtime/documents

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt numpy scipy scikit-learn

# Copy backend application
COPY backend/ /app/backend/
WORKDIR /app/backend

# Copy built frontend assets to the expected location
COPY --from=frontend-builder /build/dist /app/frontend/dist

# Expose API and frontend server port
EXPOSE 5000

# Default entrypoint runs waitress production server
CMD ["python", "-m", "waitress", "--port=5000", "--call", "app:create_app"]
