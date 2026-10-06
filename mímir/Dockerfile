# Build context: repository root (the service reuses the root models.py).
FROM python:3.14-slim AS base

# Install Python dependencies into an isolated prefix. The pip cache mount
# keeps downloaded wheels between builds, so packages are not re-downloaded
# on every `docker build`.
COPY mímir/requirements.txt ./requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install -r requirements.txt


FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /logos/mímir

# Reuse the packages installed in the dependencies stage.
COPY --from=base /install /usr/local

# Logos ORM models and database config shared with the CLI importers.
COPY database.py models.py ratios.py /logos/

# Alembic migrations (config, environment and revision scripts).
COPY alembic.ini /logos/
COPY alembic /logos/alembic

# Service source.
COPY mímir/app ./app

# Apply pending migrations on startup, then start the API server.
COPY mímir/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 8443

CMD ["python", "-m", "app.main"]
