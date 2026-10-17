# Deploy GoalStats to Render

Local Make commands and Compose remain unchanged. Production uses injected environment
variables, external PostgreSQL/Redis, and Gunicorn; it never reads `.env.local`.
The default Docker image serves the API. Named `runtime` and `tooling` targets remain available.

## Render settings

| Setting | Value |
| --- | --- |
| Service / runtime | Web Service / Docker |
| Repository | `WestiferRobin/goal-stats-service` |
| Branch | Approved branch containing these changes; `master` after merge |
| Root directory | Leave blank (repository root) |
| Dockerfile / context | `./Dockerfile` / `.` |
| Build command | None; Render builds the Dockerfile |
| Health check path | `/ready` |
| Region | Near external PostgreSQL and Redis |
| Disk | None |
| Auto-deploy | Off initially; manually deploy the reviewed commit |
| Compute | Free for initial preview; paid compute for sustained availability |

Choose one migration procedure below. Free has 512 MB RAM and idle spin-down/cold starts;
production workload capacity has not been certified. References:
[Docker](https://render.com/docs/docker), [deploys](https://render.com/docs/deploys),
[Free limitations](https://render.com/docs/free).

## Environment variables

Set these in Render Environment settings. Examples contain no real credentials.

| Variable | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `DATABASE_URL` | `postgresql+psycopg://goalstats_app:REPLACE_ME@db.example.com:5432/goalstats?sslmode=verify-full&sslrootcert=system` |
| `REDIS_URL` | `rediss://default:REPLACE_ME@cache.example.com:6379/0` |
| `SERVICE_API_TOKEN` | Random secret, at least 32 printable ASCII characters, no whitespace |
| `CACHE_KEY_PREFIX` | `goal-stats-service:production:v1` (also the production default) |
| `CACHE_TTL_SECONDS` | `300` |
| `OPENAPI_ENABLED` | `false` |
| `LOG_LEVEL` | `INFO` |
| `FLASK_SKIP_DOTENV` | `1` |

Let Render supply `PORT` (normally `10000`); Gunicorn and Docker health checks use it,
with fallback `8000`. Do not set local `APP_PORT`, `HOST_APP_PORT`, `POSTGRES_PORT`, or
`REDIS_PORT`. `API_FOOTBALL_KEY` is unnecessary for the current API.

Generate the token privately: `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`.
Store it in deployment secrets, never source control or browser configuration. Production
startup and the migration CLI reject a missing/invalid token. Redis may be omitted;
the API then uses its existing degraded readiness policy.

URL-encode provider credentials. PostgreSQL accepts `postgresql://` and
`postgresql+psycopg://`, not `postgres://`, with only supported TLS query parameters.
For a private CA, mount a secret certificate and replace `sslrootcert=system` with its
absolute readable path, such as `/etc/secrets/postgres-ca.pem`. Redis accepts `redis://`
and `rediss://` without query parameters; use TLS for external connections. Allow Render
through provider firewalls and check provider connection limits.

## Database and migrations

Provision a durable PostgreSQL database (17 matches local) and a role allowed to create
and alter its application tables. Use a direct database endpoint for migrations.
Alembic initializes a fresh database; no SQL import or revision stamping is needed.
Never run the fresh-database SQL export against an existing installation.

For existing data, verify backups and inspect the current revision and legacy tables
before deployment. Retirement migrations refuse populated legacy tables, unexpected
ownership, or dependencies. Resolve refusals separately; do not delete records or stamp
over failures. Database timeouts are bounded, so lock contention may abort migrations.
Do not run concurrent migration jobs/deploys.

### Paid: separate pre-deploy migration

- Pre-Deploy Command: `alembic upgrade head`
- Docker Command: leave blank; normal image startup never migrates.

A failed pre-deploy command prevents promotion. `/ready` also checks the exact Alembic
head and application tables, so a missing/stale schema cannot pass readiness.

### Free: explicit migrate-before-serve command

Free has no pre-deploy command. Leave that field blank and set **Docker Command** to:

```sh
/bin/sh /app/scripts/deployment/start.sh --migrate
```

This runs `alembic upgrade head` once in the startup process, then replaces that process
with Gunicorn. It does not migrate in workers. Failure exits before the HTTP listener
starts. It runs again on restarts/cold starts; an already-current database is a no-op.
Keep one service instance and serialize migration operations. Old instances may still
serve during deployment; schema changes must remain compatible with them.

Alternatively, run `alembic upgrade head` from a trusted operator environment with the
same reviewed code and injected production variables, then leave Docker Command blank.
Never use local Make commands for production migrations or put credential URLs in shell
history/command arguments. Keep production variables out of your local-development shell.

Startup never seeds. Readiness can succeed with an empty catalog. Historical data needs
the approved source and existing cloud importer: `--target cloud`, exact expected host
and database, `--confirm-production`, and verified TLS. Raw sources are intentionally
excluded from the image. See [import operations](football.md#historical-import-operations).

## Authenticate goal-stats-app

Production requires `Authorization: Bearer <SERVICE_API_TOKEN>` on every method except
GET, HEAD, and OPTIONS. Missing/incorrect credentials return 401 before domain handlers.
Reads and health endpoints stay public; local/dev/test behavior is unchanged.

Set these **server-only** variables in the frontend deployment:

```text
FOOTBALL_API_BASE_URL=https://YOUR-SERVICE.onrender.com
SERVICE_API_TOKEN=<same secret as backend>
```

The frontend proxy appends `/api/v1`. Its server-side fetch helper must set the backend
header itself, replacing any browser-provided Authorization value:

```ts
const headers = new Headers(existingHeaders);
headers.set('Authorization', `Bearer ${process.env.SERVICE_API_TOKEN}`);
// Pass headers to the existing backend fetch, preserving method/body handling.
```

Never use a `NEXT_PUBLIC_` variable or expose the token to the browser. The proxy must
enforce intended user permissions before forwarding mutations: this token authenticates
the frontend server, not individual users. Browser calls remain same-origin through the
proxy; no backend CORS change is required. The frontend repository is not modified here.

## Deployment verification

After the approved changes are pushed and Render builds the selected commit:

1. Logs must show Gunicorn listening on `0.0.0.0:<PORT>` without worker boot errors.
2. `curl -i https://YOUR-SERVICE.onrender.com/health` must return `200 Healthy`.
3. `curl -i https://YOUR-SERVICE.onrender.com/ready` must return `200 Healthy`, or
   `200 Degraded` for Redis unavailability. Database/schema failure returns 503.
   Docker and Render accept both successful readiness states.
4. `GET /api/v1/catalog/teams` must return 200 (empty is valid before import).
5. POST JSON `{}` to `/api/v1/scenarios` without authentication: expect 401.
   Through the authenticated frontend proxy, expect 400 validation failure. This checks
   authentication without creating records.
6. Exercise a valid workflow through the frontend using authorized test data.

Local tests/builds do not verify Render networking, provider credentials/TLS, or frontend
integration. Record the deployed commit and actual results before declaring it operational.
