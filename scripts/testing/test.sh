#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
root=$PWD
mode=test
if [[ $# -eq 1 && $1 == certify ]]; then
  mode=certify
elif [[ $# -ne 0 ]]; then
  echo 'Use make test or make certify; no other arguments are supported.' >&2
  exit 2
fi
# Normalize interpreter settings locally before even verifying the repository Python.
# Provider, pytest, Compose, and coverage overrides remain fail-closed below.
unset PYTHONSTARTUP PYTHONPATH PYTHONHOME PYTHONUSERBASE PYTHONINSPECT PYTHONOPTIMIZE \
  PYTHONBREAKPOINT PYTHONWARNINGS PYTHONPYCACHEPREFIX PYTHONSAFEPATH
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
for key in DATABASE_URL REDIS_URL TEST_DATABASE_URL TEST_REDIS_URL TEST_SESSION_MANIFEST \
  TEST_PINNED_SOURCE APP_ENV POSTGRES_USER POSTGRES_PASSWORD REDIS_PASSWORD TEST_PROJECT TEST_SESSION \
  TEST_DATABASE_DISPOSABLE TEST_REDIS_DISPOSABLE TEST_RUNNER_HOSTNAME TEST_TOOLING_IMAGE \
  COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES COMPOSE_ENV_FILES COMPOSE_PATH_SEPARATOR \
  PYTEST_ADDOPTS PYTEST_PLUGINS \
  COVERAGE_FILE COVERAGE_PROCESS_START COVERAGE_RCFILE; do
  if [[ -n ${!key+x} ]]; then
    echo "Error: conflicting inherited $key; unset it before testing (value omitted)." >&2
    exit 2
  fi
done
# Reject all selector/debug/plugin overrides, including future tool environment keys.
for key in $(compgen -v); do
  case "$key" in
    COVERAGE_*|PYTEST_*|COMPOSE_*)
      echo "Error: conflicting inherited $key; unset it before testing (value omitted)." >&2
      exit 2 ;;
  esac
done
python="$root/.venv/bin/python"
if [[ ! -x "$python" ]] || ! "$python" -B scripts/development/python_environment.py verify; then
  echo 'Error: valid repository Python 3.12 .venv required; run make setup.' >&2
  exit 2
fi
export PYTHONPATH="$root/src:$root/scripts/development:$root/scripts/database:$root/scripts/testing"
command -v docker >/dev/null || { echo 'Error: Docker is required.' >&2; exit 2; }
docker info >/dev/null 2>&1 || { echo 'Error: Docker is not running.' >&2; exit 2; }
umask 077
project="goal-stats-service-test-$("$python" -B -c 'import secrets; print(secrets.token_hex(12))')"
export TEST_PROJECT="$project"
export TEST_SESSION=$("$python" -B -c 'import secrets; print(secrets.token_hex(24))')
export POSTGRES_USER="test_$("$python" -B -c 'import secrets; print(secrets.token_hex(12))')"
export POSTGRES_PASSWORD="test-$("$python" -B -c 'import secrets; print(secrets.token_hex(24))')"
export REDIS_PASSWORD="test-$("$python" -B -c 'import secrets; print(secrets.token_hex(24))')"
[[ ! -L .host-sessions ]] || { echo 'Unsafe session directory.' >&2; exit 2; }
mkdir -p .host-sessions
temporary=$(mktemp -d "$root/.host-sessions/${project}.XXXXXX")
temporary=$(cd "$temporary" && pwd -P)
source_directory="$temporary/pinned-source"
source_started=false
export TEST_SESSION_MANIFEST="$temporary/owned-test.json"
: >"$temporary/empty.env"
compose=(docker compose --env-file "$temporary/empty.env" -p "$project" -f docker/compose.test.yml)
started=false
active_pid=
completed=false
reports=
cleanup_failure() {
  echo "Cleanup failed: $1" >&2
  if [[ "$status" -eq 0 ]]; then status=1; fi
}
cleanup() {
  status=$?
  if [[ "$status" -eq 0 && "$completed" != true ]]; then status=1; fi
  trap - EXIT
  trap '' INT TERM
  if [[ -n "$active_pid" ]]; then
    kill -TERM "$active_pid" 2>/dev/null || true
    wait "$active_pid" 2>/dev/null || true
  fi
  if [[ -n "$reports" ]] && ! rm -f -- "$reports/.coverage"; then
    cleanup_failure 'raw coverage cleanup failed'
  fi
  if [[ "$started" == true ]]; then
    "${compose[@]}" down --remove-orphans >/dev/null || cleanup_failure 'Docker providers'
    "$python" -B scripts/testing/test_resources.py absent "$project" || cleanup_failure 'owned resources remain'
  fi
  if [[ -f "$temporary/baseline.json" ]]; then
    "$python" -B scripts/testing/test_resources.py preserved "$temporary/baseline.json" || cleanup_failure 'resource preservation'
  fi
  source_clean=true
  if [[ "$source_started" == true ]]; then
    if ! "$python" -B scripts/testing/pinned_source.py cleanup "$source_directory" "$TEST_SESSION"; then
      cleanup_failure 'owned source mount/artifacts; session retained for recovery'
      source_clean=false
    fi
  fi
  if [[ "$source_clean" == true ]]; then
    rm -rf -- "$temporary" || cleanup_failure 'private session directory'
  fi
  if [[ "$status" -eq 0 && "$completed" == true ]]; then
    if [[ "$mode" == certify ]]; then
      echo 'Certification: PASS (tests, coverage, and cleanup)'
    else
      echo 'Canonical test workflow: PASS (tests and cleanup)'
    fi
  elif [[ "$mode" == certify ]]; then
    echo 'Certification: FAIL' >&2
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
execute_mode() {
  "$python" -B scripts/testing/test_ownership.py "$@" &
  active_pid=$!
  if wait "$active_pid"; then
    active_pid=
  else
    result=$?
    active_pid=
    return "$result"
  fi
}
execute() { execute_mode execute "$@"; }
owned_run() { execute_mode owned "$python" -B "$@"; }
"$python" -B scripts/testing/test_resources.py snapshot "$temporary/baseline.json"
"$python" -B scripts/testing/test_resources.py available "$project"
echo 'Running host lint, formatting, and strict type checks...'
execute "$root/.venv/bin/ruff" check --no-cache .
execute "$root/.venv/bin/ruff" format --check --no-cache .
execute "$python" -B -m mypy --config-file=mypy.ini --cache-dir="$temporary/mypy-cache"
if [[ "$mode" == certify ]]; then
  reports=$(mktemp -d "$root/.host-sessions/certify-${project}.XXXXXX")
  export COVERAGE_FILE="$reports/.coverage"
  echo "Certification reports: $reports"
  source_started=true
  execute "$python" -B scripts/testing/pinned_source.py prepare "$source_directory" "$TEST_SESSION"
  export TEST_PINNED_SOURCE="$source_directory/mount/results.csv"
fi
echo "Owned test project: $project"
started=true
execute "${compose[@]}" up -d --wait --wait-timeout 90 postgres redis
"$python" -B scripts/testing/test_resources.py receipt "$project" "$TEST_SESSION" "$TEST_SESSION_MANIFEST"
owned_run -m alembic upgrade head
if [[ "$mode" == test ]]; then
  echo 'Running host Unit + Integration tests...'
  owned_run -m pytest -q -p no:cacheprovider -m 'not pinned_source' tests/unit tests/integration
else
  echo 'Measuring host Unit + Integration coverage...'
  test_status=0
  owned_run -m coverage run --rcfile=.coveragerc -m pytest -q -p no:cacheprovider \
    --junitxml="$reports/tests.xml" tests/unit tests/integration || test_status=$?
  report_status=0
  execute "$python" -B scripts/testing/coverage_report.py "$reports" || report_status=$?
  if [[ ! -s "$reports/coverage.json" || ! -s "$reports/coverage.xml" ]]; then
    echo 'Certification reports missing or empty.' >&2
    if [[ "$test_status" -ne 0 ]]; then exit "$test_status"; fi
    if [[ "$report_status" -ne 0 ]]; then exit "$report_status"; fi
    exit 1
  fi
  if [[ "$test_status" -ne 0 ]]; then
    echo "Unit/Integration execution failed (exit $test_status); coverage is diagnostic only." >&2
    exit "$test_status"
  fi
  if [[ "$report_status" -ne 0 ]]; then
    echo 'Tests passed; coverage gate or reporting failed. See coverage summary above.' >&2
    exit "$report_status"
  fi
fi
completed=true
