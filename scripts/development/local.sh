#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

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
  app_port=$("$python" scripts/development/python_environment.py config)
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

seed_data() {
  [[ -z ${DRY_RUN+x} ]] || fail 'DRY_RUN is unsupported; use DRY=true or DRY=false.'
  dry=${DRY-false}
  [[ "$dry" == true || "$dry" == false ]] || fail 'DRY must be exactly true or false.'
  approved=(womens-world-cup-1991 womens-world-cup-1995 womens-world-cup-1999
    womens-world-cup-2003 womens-world-cup-2007 womens-world-cup-2011
    womens-world-cup-2015 womens-world-cup-2019 womens-world-cup-2023)
  datasets=()
  if [[ ${DATASET-} == womens-world-cup ]]; then
    datasets=("${approved[@]}")
  else
    for candidate in "${approved[@]}"; do
      if [[ ${DATASET-} == "$candidate" ]]; then datasets=("$candidate"); fi
    done
  fi
  [[ ${#datasets[@]} -gt 0 ]] || fail 'DATASET must be womens-world-cup or an approved individual edition.'
  for key in COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES COMPOSE_ENV_FILES COMPOSE_PATH_SEPARATOR; do
    [[ -z ${!key+x} ]] || fail "Unsupported inherited $key (value omitted)."
  done
  source_directory=data/raw/martj42-womens-results/1855e313ae8bcd0330426e62c8e4cf15ce45077c
  [[ -d "$source_directory" && -f "$source_directory/results.csv" ]] || fail 'Pinned results.csv is missing; prepare the approved source separately.'
  source_directory=$(cd "$source_directory" && pwd -P)
  if command -v cygpath >/dev/null 2>&1; then source_directory=$(cygpath -m "$source_directory"); fi
  check_tools
  select_python
  validate_config
  docker image inspect goal-stats-service:runtime >/dev/null 2>&1 || fail 'Runtime image missing; run make setup separately.'
  provider=$("${compose[@]}" ps --status running -q postgres)
  [[ -n "$provider" ]] || fail 'PostgreSQL is not running; prepare providers and schema separately.'
  [[ $(docker inspect --format '{{.State.Health.Status}}' "$provider") == healthy ]] || fail 'PostgreSQL is not healthy.'
  docker network inspect "${project}_default" >/dev/null 2>&1 || fail 'Local network missing; prepare providers separately.'

  temporary=$(mktemp -d "${TMPDIR:-/tmp}/goalstats-seed.XXXXXX")
  runner="goalstats-seed-$("$python" -B -c 'import secrets; print(secrets.token_hex(12))')"
  active_pid=
  completed=()
  current=preflight
  index=0
  total_teams=0 total_competitions=0 total_matches=0
  seed_cleanup() {
    status=$?
    trap - EXIT
    trap '' INT TERM
    if [[ -n "$active_pid" ]]; then
      docker rm -f "$runner" >/dev/null 2>&1 || true
      kill -TERM "$active_pid" 2>/dev/null || true
      wait "$active_pid" 2>/dev/null || true
    fi
    if [[ $status -ne 0 ]]; then
      docker rm -f "$runner" >/dev/null 2>&1 || true
      echo "Seed FAILED: $current; confirmed completed: ${completed[*]:-none}." >&2
      echo "Not attempted: ${datasets[*]:$index}. Earlier confirmed commits remain; an interrupted/failed commit may be unconfirmed. Retry safely after reviewing the importer error." >&2
    fi
    rm -rf "$temporary"
    exit "$status"
  }
  trap seed_cleanup EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  seed_execute() {
    env MSYS_NO_PATHCONV=1 "${compose[@]}" run --rm --no-deps -T --pull never \
      --name "$runner" --volume "$source_directory:/input:ro" app "$@" \
      >"$temporary/output" &
    active_pid=$!
    result=0
    wait "$active_pid" || result=$?
    active_pid=
    cat "$temporary/output"
    return "$result"
  }
  # Compare operative code/schema/contracts and pinned requirements before any import.
  # Compose mounts src read-only; data, Alembic and requirements come from the image.
  fingerprint_code='import hashlib,json
from pathlib import Path
paths=[Path("requirements.txt"),Path("alembic.ini")]
for directory in ("src","alembic","data/womens-world-cup","data/verification"):
 paths.extend(p for p in Path(directory).rglob("*") if p.is_file() and p.suffix in (".py",".json"))
print(hashlib.sha256(json.dumps([(str(p),hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(paths)],separators=(",",":")).encode()).hexdigest())'
  expected=$("$python" -B -c "$fingerprint_code")
  if ! seed_execute python -B -c "$fingerprint_code" >/dev/null; then
    fail 'Cannot inspect prepared image; run make setup separately.'
  fi
  [[ $(cat "$temporary/output") == "$expected" ]] || fail 'Runtime image is outdated; run make setup separately before seeding.'
  echo "Seed selection: $DATASET; DRY=$dry; editions: ${#datasets[@]}"
  if [[ "$dry" == true ]]; then
    echo 'Dry-run counts are edition-local estimates; shared teams are not summed. Each edition has its own read-only snapshot.'
  else
    echo 'Each edition commits independently; the group is not globally atomic.'
  fi
  for current in "${datasets[@]}"; do
    index=$((index + 1))
    echo "Edition $index/${#datasets[@]}: $current"
    arguments=(flask --app 'main:create_app()' import-football
      --dataset "$current" --directory /input --target local
      --expect-host postgres --expect-database goal_stats_service_local)
    [[ "$dry" == false ]] || arguments+=(--dry-run)
    seed_execute "${arguments[@]}"
    counts=$("$python" -B -c 'import json,sys
r=json.load(open(sys.argv[1])); dry=sys.argv[2]=="true"
assert r["committed"] is (not dry) and r["insert_counts"] == ("proposed" if dry else "committed")
values=[r[k] for k in ("teams_inserted","competitions_inserted","matches_inserted")]
assert all(type(v) is int and v>=0 for v in values)
print(*values)' "$temporary/output" "$dry")
    read -r teams competitions matches <<< "$counts"
    completed+=("$current")
    total_teams=$((total_teams + teams))
    total_competitions=$((total_competitions + competitions))
    total_matches=$((total_matches + matches))
  done
  echo "Seed SUCCESS; completed: ${completed[*]}; failed: none; not attempted: none."
  if [[ "$dry" == false ]]; then
    echo "Confirmed committed inserts: teams=$total_teams competitions=$total_competitions matches=$total_matches"
  fi
}

case "$action" in
  seed)
    seed_data
    ;;
  help)
    printf '%s\n' \
      'GoalStats backend — one configuration and database' \
      '  make setup   Prepare Python 3.12 .venv, configuration, and Docker images; start nothing' \
      '  make infra   PostgreSQL + Redis only; stop this project Docker Flask' \
      '  make run     Host Flask + Docker PostgreSQL/Redis; foreground development' \
      '  make deploy  Deploy the complete backend locally in Docker. No cloud deployment.' \
      '  make seed    Import approved history; DATASET required, DRY=true|false (default false)' \
      '  make test    Run lint, format, types, and isolated unit/integration tests' \
      '  make stop    Stop Docker resources; preserve data. Stop host Flask with Ctrl-C or IDE Stop.' \
      '  make help    Show these eight commands' \
      '' 'First run: make setup && make run' \
      'Swagger: http://127.0.0.1:5100/swagger' \
      'Run lifecycle commands sequentially, not concurrently.'
    ;;
  setup)
    check_tools
    select_python
    prepare_env
    validate_config
    "$python" scripts/development/python_environment.py bootstrap
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
      "$python" scripts/development/python_environment.py verify
    fi
    if [[ "$action" == deploy ]]; then
      # A repeated deployment may already own the listener. Do not stop it.
      if [[ -z $("${compose[@]}" ps --status running -q app) ]] ||
         [[ $("${compose[@]}" port app 8000) != "127.0.0.1:$app_port" ]]; then
        "$python" scripts/development/python_environment.py port
      fi
    else
      "${compose[@]}" stop app
      "$python" scripts/development/python_environment.py port
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
    select_python
    validate_config
    "${compose[@]}" down --remove-orphans
    echo 'Docker resources stopped. PostgreSQL data preserved.'
    echo 'Stop host Flask with Ctrl-C or IDE Stop; a running host process has lost its providers.'
    ;;
  *) fail 'Use setup, infra, run, deploy, seed, test, stop, or help.' ;;
esac
