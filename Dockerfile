# syntax=docker/dockerfile:1.7

FROM node:24.4.1-alpine3.22@sha256:820e86612c21d0636580206d802a726f2595366e1b867e564cbc652024151e8a AS web-build
WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund

COPY index.html tsconfig.json tsconfig.app.json tsconfig.node.json vite.config.ts ./
COPY public ./public
COPY src ./src
RUN npm run build


FROM python:3.13.5-slim-bookworm@sha256:4c2cf9917bd1cbacc5e9b07320025bdb7cdf2df7b0ceaccb55e9dd7e30987419 AS python-build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv

RUN python -m venv "${VIRTUAL_ENV}"
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

COPY scripts/requirements-container.lock /tmp/requirements-container.lock
RUN python -m pip install --require-hashes --no-deps -r /tmp/requirements-container.lock

COPY backend /src/backend
RUN python -m pip install --no-deps --no-build-isolation /src/backend


FROM python:3.13.5-slim-bookworm@sha256:4c2cf9917bd1cbacc5e9b07320025bdb7cdf2df7b0ceaccb55e9dd7e30987419 AS runtime
ARG APP_UID=10001
ARG APP_GID=10001

ENV AGENCY_WEB_DIST=/app/static \
    PATH="/opt/venv/bin:${PATH}" \
    PORT=8080 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=python-build /opt/venv /opt/venv
COPY --from=python-build --chown=${APP_UID}:${APP_GID} /src/backend/alembic.ini /app/backend/alembic.ini
COPY --from=python-build --chown=${APP_UID}:${APP_GID} /src/backend/migrations /app/backend/migrations
COPY --from=web-build --chown=${APP_UID}:${APP_GID} /build/dist /app/static
COPY --chown=${APP_UID}:${APP_GID} scripts/start_container.py /app/scripts/start_container.py
COPY --chown=${APP_UID}:${APP_GID} scripts/run_cloud_migrations.py /app/scripts/run_cloud_migrations.py

USER ${APP_UID}:${APP_GID}
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT','8080'), timeout=2).read()"]

CMD ["python", "/app/scripts/start_container.py"]
