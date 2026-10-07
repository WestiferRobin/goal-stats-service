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
  make_version=$(make --version) || fail 'GNU Make is required.'
  [[ "$make_version" == *'GNU Make'* ]] || fail 'GNU Make is required.'
  docker compose version >/dev/null || fail 'Docker Compose v2 is required.'
  docker info >/dev/null 2>&1 || fail 'Docker is not running. Start it and retry.'
}

prepare_env() {
  [[ -f "$example" ]] || fail '.env.example is missing.'
  if [[ ! -e "$env_file" && ! -L "$env_file" ]]; then
    cp "$example" "$env_file"
    chmod 600 "$env_file" 2>/dev/null || true
    echo 'Created .env.local from .env.example.'
  elif [[ ! -f "$env_file" || -L "$env_file" ]]; then
    fail '.env.local must be a regular file, not a directory or symlink.'
  else
    echo 'Preserving existing .env.local.'
  fi
  grep -Eq '^POSTGRES_PASSWORD=.+$' "$env_file" || fail '.env.local requires a nonempty POSTGRES_PASSWORD.'
}

select_python() {
  python=${PYTHON:-python3.12}
  command -v "$python" >/dev/null || fail 'Python 3.12 is required. Install it or set PYTHON to its executable. Native Windows host development requires WSL.'
  "$python" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else "Python 3.12 is required.")'
}

validate_config() {
  [[ -f "$env_file" ]] || fail '.env.local is missing. Run make setup first.'
  app_port=$("$python" scripts/python_environment.py config)
  # local_runtime rejects conflicting inherited values before Compose can use them.
  "${compose[@]}" config --quiet
}

providers() {
  step 'Starting PostgreSQL and Redis'
  "${compose[@]}" up -d --wait --wait-timeout 90 postgres redis
}

prepare_database() {
  step 'Applying database migrations'
  "${compose[@]}" run --rm --no-deps -T app alembic upgrade head
  step 'Importing bundled football data'
  "${compose[@]}" run --rm --no-deps -T app flask --app 'main:create_app()' import-football
}

build_app() {
  step 'Building the backend'
  "${compose[@]}" build app
}

urls() {
  echo "  API:     http://127.0.0.1:$app_port"
  echo "  Swagger: http://127.0.0.1:$app_port/swagger"
  echo "  Health:  http://127.0.0.1:$app_port/health"
  echo "  Ready:   http://127.0.0.1:$app_port/ready"
}

case "$action" in
  help)
    printf '%s\n' \
      'GoalStats backend — one configuration and database' \
      '  make setup   Prepare Python 3.12 .venv, configuration, and Docker images; start nothing' \
      '  make infra   PostgreSQL + Redis only; stop this project Docker Flask' \
      '  make run     Host Flask + Docker PostgreSQL/Redis; foreground development' \
      '  make deploy  Deploy the complete backend locally in Docker. No cloud deployment.' \
      '  make test    Run lint, format, types, and isolated unit/integration tests' \
      '  make stop    Stop Docker resources; preserve data. Stop host Flask with Ctrl-C or IDE Stop.' \
      '  make help    Show these seven commands' \
      '' 'First run: make setup && make run' \
      'Swagger: http://127.0.0.1:5100/swagger' \
      'Run lifecycle commands sequentially, not concurrently.'
    ;;
  setup)
    check_tools
    select_python
    prepare_env
    validate_config
    "$python" scripts/python_environment.py bootstrap
    build_app
    docker build --target tooling -t goal-stats-service:tooling .
    "${compose[@]}" pull postgres redis
    echo 'Setup complete; no services started. Next: make run (host), make deploy (Docker), or make infra.'
    ;;
  infra|run|deploy)
    check_tools
    select_python
    validate_config
    if [[ "$action" == run ]]; then
      "$python" scripts/python_environment.py verify
    fi
    if [[ "$action" == deploy ]]; then
      # A repeated deployment may already own the listener. Do not stop it.
      if [[ -z $("${compose[@]}" ps --status running -q app) ]] ||
         [[ $("${compose[@]}" port app 8000) != "127.0.0.1:$app_port" ]]; then
        "$python" scripts/python_environment.py port
      fi
    else
      "${compose[@]}" stop app
      "$python" scripts/python_environment.py port
    fi
    if [[ "$action" == infra ]]; then
      providers
      echo 'PostgreSQL and Redis ready; no Flask started.'
      exit 0
    fi
    build_app
    providers
    prepare_database
    if [[ "$action" == run ]]; then
      echo 'Starting host Flask; Ctrl-C stops Flask and leaves infrastructure running.'
      urls
      exec .venv/bin/python src/main.py
    fi
    step 'Starting Docker Flask'
    "${compose[@]}" up -d --wait --wait-timeout 90 app
    echo 'Local Docker deployment ready:'
    urls
    ;;
  stop)
    check_tools
    [[ -f "$env_file" ]] || fail '.env.local is missing. Nothing is configured to stop.'
    "${compose[@]}" down --remove-orphans
    echo 'Docker resources stopped. PostgreSQL data preserved.'
    echo 'Stop host Flask with Ctrl-C or IDE Stop; a running host process has lost its providers.'
    ;;
  *) fail 'Use setup, infra, run, deploy, test, stop, or help.' ;;
esac
