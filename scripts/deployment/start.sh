#!/bin/sh
set -eu

# Explicit single-process migration option for Render Free (no pre-deploy hook).
# No listener or workers start if migration fails. Normal startup never migrates.
case "$#:$*" in
  0:) ;;
  1:--migrate) alembic upgrade head ;;
  *) echo 'Usage: start.sh [--migrate]' >&2; exit 2 ;;
esac

exec gunicorn --bind "0.0.0.0:${PORT:-8000}" --workers=2 \
  --timeout=30 --graceful-timeout=10 --no-control-socket \
  --access-logfile=- --error-logfile=- 'main:create_app()'
