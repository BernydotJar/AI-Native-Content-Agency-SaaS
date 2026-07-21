# syntax=docker/dockerfile:1.7
FROM node:22-bookworm-slim AS web-build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig*.json vite.config.ts .oxlintrc.json ./
COPY public ./public
COPY src ./src
RUN npm run build

FROM python:3.12-slim AS backend-build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY backend/requirements-build.lock ./requirements-build.lock
RUN python -m pip install --no-cache-dir --require-hashes -r requirements-build.lock
COPY backend ./backend
RUN python -m build --no-isolation --wheel --outdir /wheels ./backend

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080 \
    AGENCY_STATIC_DIR=/app/dist \
    AGENCY_MEMORY_DB=:memory:
WORKDIR /app
RUN addgroup --system --gid 10001 agency \
    && adduser --system --uid 10001 --ingroup agency --home /nonexistent --no-create-home agency
COPY backend/requirements.lock ./backend/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes -r backend/requirements.lock
COPY --from=backend-build /wheels /wheels
RUN python -m pip install --no-cache-dir --no-deps /wheels/*.whl \
    && python -m pip check \
    && rm -rf /wheels
COPY --from=web-build /app/dist ./dist
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/readyz', timeout=2)" || exit 1
CMD ["agency-api"]
