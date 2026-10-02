#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

command -v docker >/dev/null || { echo 'Error: Docker is required.' >&2; exit 2; }
docker info >/dev/null 2>&1 || { echo 'Error: Docker is not running.' >&2; exit 2; }

project="goal-stats-service-test-$(printf '%06x%06x' "$RANDOM" "$RANDOM")"
password="test-$RANDOM-$RANDOM-$RANDOM"
runner="${project}-runner"
mkdir -p .host-sessions
temporary=$(mktemp -d ".host-sessions/${project}.XXXXXX")
receipt="$temporary/owned-test.json"
empty_env="$temporary/empty.env"
: >"$empty_env"
export POSTGRES_PASSWORD="$password"
export OPENAPI_ENABLED=true LOG_LEVEL=INFO CACHE_TTL_SECONDS=300
export TEST_RUNNER_HOSTNAME="$runner"
started=false

cleanup() {
  status=$?
  trap - EXIT INT TERM
  docker rm -f "$runner" >/dev/null 2>&1 || true
  if [[ "$started" == true ]]; then
    if (( status != 0 )); then "${compose[@]}" logs --no-color --tail 100 >&2 || true; fi
    "${compose[@]}" down --volumes --remove-orphans >/dev/null || status=1
  fi
  rm -rf "$temporary"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

cat >"$receipt" <<EOF
{"hostname":"$runner","TEST_DATABASE_URL":"postgresql+psycopg://goalstats:$password@postgres:5432/goalstats_test_runtime","TEST_REDIS_URL":"redis://redis:6379/0"}
EOF
chmod 644 "$receipt"
if command -v cygpath >/dev/null 2>&1; then
  host_receipt=$(cygpath -m "$receipt")
  host_empty_env=$(cygpath -m "$empty_env")
else
  host_receipt=$(cd "$(dirname "$receipt")" && pwd)/$(basename "$receipt")
  host_empty_env=$(cd "$(dirname "$empty_env")" && pwd)/$(basename "$empty_env")
fi
compose=(docker compose --env-file "$host_empty_env" -p "$project" -f docker/compose.test.yml)

echo 'Building test image...'
docker build --target tooling -t goal-stats-service:tooling .

echo 'Running lint, formatting, and strict type checks...'
docker run --rm --network none goal-stats-service:tooling ruff check --no-cache .
docker run --rm --network none goal-stats-service:tooling ruff format --check --no-cache .
MSYS2_ARG_CONV_EXCL='--cache-dir=' docker run --rm --network none \
  goal-stats-service:tooling mypy --cache-dir=/tmp/mypy-cache

echo 'Starting disposable test providers...'
started=true
"${compose[@]}" up -d --wait --wait-timeout 90 postgres redis

echo 'Applying migrations to the disposable test database...'
"${compose[@]}" run --rm --no-deps -T runner alembic upgrade head

echo 'Running unit and integration tests...'
MSYS_NO_PATHCONV=1 "${compose[@]}" run --rm --no-deps -T --name "$runner" \
  -v "$host_receipt:/run/owned-test.json:ro" runner \
  pytest -q -p no:cacheprovider tests/unit tests/integration

echo 'All contributor checks passed.'
