FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements-models.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt -r backend/requirements-models.txt
COPY backend/ ./backend/
COPY --from=frontend /build/dist ./frontend/dist/
RUN useradd --uid 10001 --create-home onecase && mkdir -p /app/.runtime && chown -R onecase:onecase /app
USER onecase
EXPOSE 5000
CMD ["waitress-serve", "--host=0.0.0.0", "--port=5000", "--call", "backend.app:create_app"]
