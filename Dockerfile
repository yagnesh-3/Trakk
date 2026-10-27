# One container: the API also serves the built web app, so the browser uses a single origin.

FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
RUN useradd --create-home tracker
USER tracker
ENV ENVIRONMENT=production STATIC_DIR=/app/frontend/dist
# Migrate, create the first admin if missing, then serve. Hosts set PORT; 8000 otherwise.
CMD alembic upgrade head \
    && python -m app.cli ensure-admin \
    && exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
