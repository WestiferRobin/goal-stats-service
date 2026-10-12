#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

[[ $# -eq 0 ]] || { echo 'Use make test without mode arguments.' >&2; exit 2; }

# Neither inherited application settings nor Compose overrides may select test targets.
for key in DATABASE_URL REDIS_URL TEST_DATABASE_URL TEST_REDIS_URL TEST_SESSION_MANIFEST \
  APP_ENV POSTGRES_PASSWORD TEST_PROJECT TEST_RUNNER_HOSTNAME COMPOSE_FILE COMPOSE_PROJECT_NAME \
  COMPOSE_PROFILES COMPOSE_ENV_FILES COMPOSE_PATH_SEPARATOR; do
  if [[ -n ${!key+x} ]]; then
    echo "Error: conflicting inherited $key; unset it before testing (value omitted)." >&2
    exit 2
  fi
done
command -v docker >/dev/null || { echo 'Error: Docker is required.' >&2; exit 2; }
docker info >/dev/null 2>&1 || { echo 'Error: Docker is not running.' >&2; exit 2; }
python=${PYTHON:-python3.12}
"$python" -B -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3,12) else "Python 3.12 is required.")'
export PYTHONDONTWRITEBYTECODE=1

project="goal-stats-service-test-$("$python" -B -c 'import secrets; print(secrets.token_hex(12))')"
password="test-$("$python" -B -c 'import secrets; print(secrets.token_hex(24))')"
runner="${project}-runner"
mkdir -p .host-sessions
temporary=$(mktemp -d ".host-sessions/${project}.XXXXXX")
receipt="$temporary/owned-test.json"
empty_env="$temporary/empty.env"
: >"$empty_env"
export POSTGRES_PASSWORD="$password" TEST_PROJECT="$project" TEST_RUNNER_HOSTNAME="$runner"
export OPENAPI_ENABLED=true LOG_LEVEL=INFO CACHE_TTL_SECONDS=300
started=false
active_pid=

if command -v cygpath >/dev/null 2>&1; then
  host_temporary=$(cygpath -m "$temporary")
else
  host_temporary=$(cd "$temporary" && pwd)
fi
compose=(docker compose --env-file "$host_temporary/empty.env" -p "$project" -f docker/compose.test.yml)

cleanup() {
  status=$?
  trap - EXIT
  trap '' INT TERM
  if [[ -n "$active_pid" ]]; then
    kill -TERM "$active_pid" 2>/dev/null || true
    wait "$active_pid" 2>/dev/null || true
  fi
  docker rm -f "${project}-quality" >/dev/null 2>&1 || true
  if [[ "$started" == true ]]; then
    # Only this invocation's unique name and Compose project are eligible for cleanup.
    docker rm -f "$runner" >/dev/null 2>&1 || true
    "${compose[@]}" down --remove-orphans >/dev/null || status=1
    "$python" -B scripts/testing/test_resources.py absent "$project" || status=1
  fi
  if [[ -f "$temporary/baseline.json" ]]; then
    "$python" -B scripts/testing/test_resources.py preserved "$temporary/baseline.json" || status=1
  fi
  rm -rf "$temporary"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Wait is interruptible even while Docker is running: traps can promptly remove owned resources.
execute() {
  "$@" &
  active_pid=$!
  if wait "$active_pid"; then
    active_pid=
  else
    result=$?
    active_pid=
    return "$result"
  fi
}

owned_run() {
  "$python" -B scripts/testing/test_resources.py receipt "$project" "$runner" "$receipt"
  execute env MSYS_NO_PATHCONV=1 "${compose[@]}" run --rm --no-deps -T --name "$runner" \
    -v "$host_temporary/owned-test.json:/run/owned-test.json:ro" \
    runner python scripts/testing/test_ownership.py "$@"
}

"$python" -B scripts/testing/test_resources.py snapshot "$temporary/baseline.json"

echo 'Building test image...'
execute docker build --target tooling -t goal-stats-service:tooling .
echo 'Running lint, formatting, and strict type checks...'
execute docker run --rm --name "${project}-quality" --label "com.docker.compose.project=$project" --network none goal-stats-service:tooling ruff check --no-cache .
execute docker run --rm --name "${project}-quality" --label "com.docker.compose.project=$project" --network none goal-stats-service:tooling ruff format --check --no-cache .
execute env MSYS2_ARG_CONV_EXCL='--cache-dir=' docker run --rm --name "${project}-quality" --label "com.docker.compose.project=$project" --network none \
  goal-stats-service:tooling mypy --cache-dir=/tmp/mypy-cache

echo "Owned test project: $project"
started=true
execute "${compose[@]}" up -d --wait --wait-timeout 90 postgres redis
owned_run alembic upgrade head

echo 'Running maintained tooling, unit, and integration tests...'
owned_run pytest -q -p no:cacheprovider tests/unit tests/integration
echo 'Canonical test workflow: PASS'
