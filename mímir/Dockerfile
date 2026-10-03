# Build context: repository root (the service reuses the root models.py).
FROM python:3.12-slim AS base

# Install Python dependencies into an isolated prefix. The pip cache mount
# keeps downloaded wheels between builds, so packages are not re-downloaded
# on every `docker build`.
COPY mímir/requirements.txt ./requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install -r requirements.txt


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /logos/mímir

# Reuse the packages installed in the dependencies stage.
COPY --from=base /install /usr/local

# Logos ORM models shared with the CLI importers.
COPY models.py /logos/

# Service source.
COPY mímir/app ./app

EXPOSE 8443

CMD ["python", "-m", "app.main"]
