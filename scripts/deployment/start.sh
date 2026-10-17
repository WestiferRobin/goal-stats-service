#!/bin/sh
set -eu

# Explicit single-process migration/bootstrap options for Render Free.
# No listener starts on failure. Normal startup never migrates or imports.
case "$#:$*" in
  0:) ;;
  1:--migrate) alembic upgrade head ;;
  2:--bootstrap\ --confirm-production) python -m football.bootstrap --confirm-production ;;
  *) echo 'Usage: start.sh [--migrate | --bootstrap --confirm-production]' >&2; exit 2 ;;
esac

exec gunicorn --bind "0.0.0.0:${PORT:-8000}" --workers=2 \
  --timeout=30 --graceful-timeout=10 --no-control-socket \
  --access-logfile=- --error-logfile=- 'main:create_app()'
