# Deploy GoalStats to Render

Local Make commands and Compose remain unchanged. Production uses injected environment
variables, external PostgreSQL/Redis, and Gunicorn; it never reads `.env.local`.
The default Docker image serves the API. Named `runtime` and `tooling` targets remain available.
The production build downloads only the approved immutable `results.csv`, verifies its
SHA-256 against the manifest, and packages it at `/app/data/bootstrap/results.csv`.
Unrelated raw data and local credentials remain excluded. A download/checksum failure
fails the build. Runtime and tooling targets retain their existing source packaging.

## Render settings

| Setting | Value |
| --- | --- |
| Service / runtime | Web Service / Docker |
| Repository | `WestiferRobin/goal-stats-service` |
| Branch | Approved branch containing these changes; `master` after merge |
| Root directory | Leave blank (repository root) |
| Dockerfile / context | `./Dockerfile` / `.` |
| Build command | None; Render builds the Dockerfile |
| Docker Command | `/bin/sh /app/scripts/deployment/start.sh --bootstrap --confirm-production` |
| Pre-Deploy Command | Leave blank, including on Free |
| Health check path | `/ready` |
| Region | Near external PostgreSQL and Redis |
| Disk | None |
| Auto-deploy | Off initially; manually deploy the reviewed commit |
| Compute | Free for initial preview; paid compute for sustained availability |

The bootstrap procedure below works on Free without shell access or one-off jobs.
Free has 512 MB RAM and idle spin-down/cold starts;
production workload capacity has not been certified. References:
[Docker](https://render.com/docs/docker), [deploys](https://render.com/docs/deploys),
[Free limitations](https://render.com/docs/free).

## Environment variables

Set these in Render Environment settings. Examples contain no real credentials.

| Variable | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `DATABASE_URL` | `postgresql+psycopg://goalstats_app:REPLACE_ME@db.example.com:5432/goalstats?sslmode=verify-full&sslrootcert=system` |
| `BOOTSTRAP_EXPECT_HOST` | Exact full external database hostname from the Render database page; must equal the URL host |
| `BOOTSTRAP_EXPECT_DATABASE` | Exact database name from the Render database page; must equal the URL database |
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
The Docker image sets `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt` and
`SSL_CERT_DIR=/etc/ssl/certs` so psycopg-binary's bundled OpenSSL uses Debian's
existing CA trust store for `sslrootcert=system`. Its compiled-in paths can point
outside Debian's certificate directories. No Render environment change is needed;
keep `sslmode=verify-full&sslrootcert=system` and do not override these image defaults
with nonexistent paths. HTTPS source downloads use Python's separate OpenSSL library,
so a successful download alone does not prove libpq can find its trusted roots.

For a private CA, mount a secret certificate and replace `sslrootcert=system` with its
absolute readable path, such as `/etc/secrets/postgres-ca.pem`. Redis accepts `redis://`
and `rediss://` without query parameters; use TLS for external connections. Allow Render
through provider firewalls and check provider connection limits.

**Use Render PostgreSQL's external URL for bootstrap**, including its full hostname.
Render's internal endpoint does not support `verify-full`; do not downgrade to
`sslmode=require` or bypass the cloud-import guards. Allow the web service's outbound
addresses in the database's external access rules. See
[Render PostgreSQL connections](https://render.com/docs/postgresql-creating-connecting).
The expected host/database must be independently copied from the intended database,
not guessed or replaced with local values. No local `.env.local` or Mac import is needed.

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

### Automatic production bootstrap (Free or paid)

Leave Pre-Deploy Command blank. Set **Docker Command** exactly to:

```sh
/bin/sh /app/scripts/deployment/start.sh --bootstrap --confirm-production
```

The single startup process (never Gunicorn workers):

1. Requires production configuration, explicit confirmation, exact target identity, and
   verified TLS. Validates all nine source selections before making database changes.
2. Takes the historical importer lock and runs Alembic `upgrade head` with existing guards.
3. Imports only when all five application tables are empty, using the existing cloud-safe
   importer for 1991, 1995, 1999, 2003, 2007, 2011, 2015, 2019, and 2023.
4. Requires exactly 44 historical teams, nine competitions, and 348 matches. Verifies
   every match's facts, participant links, edition and provenance against the pinned source.
   Edition match counts are 26, 26, 32, 32, 32, 32, 52, 52, and 64.
5. Commits and then replaces the startup process with Gunicorn.

Migrations and all imports share one outer PostgreSQL transaction; importer transactions
use savepoints. Import/verification failures roll back the whole bootstrap, including
earlier editions and newly applied migrations. No success is logged before commit.
Raw exceptions/credentials are suppressed. A lost commit acknowledgment stops startup;
the next attempt verifies whatever actually committed.

On repeat deployments, a complete catalog is verified and no importer is invoked.
Existing scenarios, predictions and separately attributed team ratings are retained.
Partial, conflicting, extra, or altered historical records are refused without repairs
or deletion. An unrelated table in the target schema also blocks bootstrap. Resolve
such failures explicitly; never reset a populated database to force startup.

Keep one service instance and serialize deployments. A competing historical import
causes safe refusal; retry after it finishes. Catalog writes are locked while bootstrapping.
Old instances may serve reads during deployment, so schema changes must remain compatible.
Gunicorn never starts on failure. `/ready` retains its database/schema and Redis policy;
the detailed historical verification runs at each bootstrap, not on every health probe.

Without startup arguments the image only serves; `--migrate` remains available for
explicit migration-only startup. Local Make/Compose commands never use bootstrap.
Free PostgreSQL expires after 30 days; use a durable database plan for retained data.

## Bootstrap failure diagnostics

A bootstrap failure exits before Gunicorn and prints only a fixed category, for example:
`Production bootstrap failed; no startup authorized. Category: TLS certificate verification failure.`
No exception text, connection URLs, credentials, hostnames, or database names are printed.

| Category | Check privately in Render settings or the database dashboard |
| --- | --- |
| Database connection or DNS | Endpoint availability, DNS, external access rules and connection limits |
| PostgreSQL authentication | Configured credentials and database role access |
| Database TLS transport verification | The cloud guard did not confirm TLS in `pg_stat_ssl`; investigate transport configuration without bypassing the guard |
| TLS certificate verification | Full external hostname and trusted CA; retain `verify-full` |
| Identity: configured hostname/database name | Compare `BOOTSTRAP_EXPECT_HOST` / `BOOTSTRAP_EXPECT_DATABASE` privately with the corresponding URL fields; failure occurs before connecting |
| Identity: connected driver hostname | Requested libpq hostname differs from the independently expected hostname; inspect connection overrides, not resolved IPs |
| Identity: connected database name | `current_database()` differs from the independently expected database |
| Identity: connected user | `current_user` differs from the URL username; inspect role configuration without relaxing the check |
| Alembic migration | Role permissions, lock contention and existing legacy migration guards |
| Historical import | Approved source and importer safeguards; do not reset existing data |
| Catalog verification | Missing, extra or conflicting historical records; resolve separately without automatic repair |

Additional categories distinguish invalid production/target/TLS configuration, source
validation, database safety guards (including a competing importer or unrelated tables),
and transaction completion. Driver authentication/TLS/connection failures take precedence
over the active stage. Other errors report the stage that failed, not an inferred root cause.
The original generic message cannot identify which category caused a previous deployment.
Likewise, the older `database identity mismatch` label cannot identify which comparison
failed; the TLS transport guard also previously fell back to that label. New identity labels distinguish all five comparisons without logging their values.
Psycopg's `info.host` (`PQhost`) retains the requested hostname when `host` and
`hostaddr` are supplied; DNS resolution is reported separately in `info.hostaddr`.
It is a connection-parameter check, not independent server authentication. Cloud
`verify-full` authenticates that hostname; the SQL checks verify database and user.
A Render proxy or DNS alias alone is not justification to remove the hostname check.
See [PostgreSQL connection status](https://www.postgresql.org/docs/current/libpq-status.html).
Do not disable TLS verification or migration guards to resolve a failed startup.

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
4. Logs must report `44 teams, 9 competitions, 348 matches verified`. Catalog teams and
   competitions endpoints must return all 44 teams and all nine editions; empty is a failure.
5. POST JSON `{}` to `/api/v1/scenarios` without authentication: expect 401.
   Through the authenticated frontend proxy, expect 400 validation failure. This checks
   authentication without creating records.
6. Exercise a valid workflow through the frontend using authorized test data.

Local tests/builds do not verify Render networking, provider credentials/TLS, or frontend
integration. Record the deployed commit and actual results before declaring it operational.
