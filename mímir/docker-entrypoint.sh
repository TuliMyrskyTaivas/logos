#!/bin/sh
set -e

# Apply any pending database migrations before starting the API server.
cd /logos
alembic upgrade head

cd /logos/mímir
exec "$@"
