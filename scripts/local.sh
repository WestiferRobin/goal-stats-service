#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

action=${1:-help}
env_file=.env.local
example=.env.example
project=goalstats-service-local
compose=(docker compose --env-file "$env_file" -p "$project" -f docker/compose.local.yml)

fail() { echo "Error: $*" >&2; exit 2; }
step() { printf '\n==> %s\n' "$1"; }

check_tools() {
  command -v docker >/dev/null || fail 'Docker is required. Install/start Docker Desktop or Docker Engine.'
  command -v make >/dev/null || fail 'GNU Make is required.'
  docker compose version >/dev/null || fail 'Docker Compose v2 is required.'
  docker info >/dev/null 2>&1 || fail 'Docker is not running. Start it and retry.'
}

prepare_env() {
  [[ -f "$example" ]] || fail '.env.example is missing.'
  if [[ ! -e "$env_file" ]]; then
    cp "$example" "$env_file"
    chmod 600 "$env_file" 2>/dev/null || true
    echo 'Created .env.local from .env.example.'
  elif [[ ! -f "$env_file" || -L "$env_file" ]]; then
    fail '.env.local must be a regular file, not a directory or symlink.'
  else
    echo 'Preserving existing .env.local.'
  fi
  grep -Eq '^POSTGRES_PASSWORD=.+$' "$env_file" || fail '.env.local requires a nonempty POSTGRES_PASSWORD.'
  "${compose[@]}" config --quiet
}

case "$action" in
  help)
    printf '%s\n' \
      'GoalStats backend' \
      '' \
      '  make setup   Prepare local configuration and Docker images; start nothing' \
      '  make run     Start database/cache, migrate, import data, and start the API' \
      '  make test    Run lint, format, types, unit tests, and isolated integration tests' \
      '  make stop    Stop this repository local stack; preserve PostgreSQL data' \
      '  make help    Show this help' \
      '' \
      'First run: make setup && make run' \
      'Swagger:   http://127.0.0.1:5100/swagger'
    ;;
  setup)
    step 'Checking required tools'
    check_tools
    step 'Preparing local configuration'
    prepare_env
    step 'Building local and test images'
    "${compose[@]}" build app
    docker build --target tooling -t goal-stats-service:tooling .
    echo
    echo 'Setup complete; no services were started. Next: make run'
    ;;
  run)
    check_tools
    [[ -f "$env_file" ]] || fail '.env.local is missing. Run make setup first.'
    prepare_env
    app_port=$(awk -F= '$1 == "APP_PORT" { sub(/^[^=]*=/, ""); print; exit }' "$env_file")
    app_port=${app_port:-5100}
    step 'Building the backend'
    "${compose[@]}" build app
    step 'Starting PostgreSQL and Redis'
    "${compose[@]}" up -d --wait --wait-timeout 90 postgres redis
    step 'Applying database migrations'
    "${compose[@]}" run --rm --no-deps -T app alembic upgrade head
    step 'Importing bundled football data'
    "${compose[@]}" run --rm --no-deps -T app flask --app 'main:create_app()' import-football
    step 'Starting the API'
    "${compose[@]}" up -d --wait --wait-timeout 90 app
    echo
    echo 'GoalStats backend is ready:'
    echo "  API:     http://127.0.0.1:$app_port"
    echo "  Swagger: http://127.0.0.1:$app_port/swagger"
    echo "  Health:  http://127.0.0.1:$app_port/health"
    echo "  Ready:   http://127.0.0.1:$app_port/ready"
    ;;
  stop)
    check_tools
    [[ -f "$env_file" ]] || fail '.env.local is missing. Nothing is configured to stop.'
    "${compose[@]}" down --remove-orphans
    echo 'GoalStats backend stopped. PostgreSQL data was preserved.'
    ;;
  *) fail 'Use setup, run, test, stop, or help.' ;;
esac
