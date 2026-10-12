# Local environment

`.env.example` is committed documentation. `.env.local` is the only persistent
developer configuration and is ignored by Git. `make setup` copies the example only
when `.env.local` does not exist; it never overwrites developer values.

| Key | Default | Meaning |
| --- | --- | --- |
| `APP_PORT` | `5100` | API host port |
| `POSTGRES_PORT` | `55432` | PostgreSQL host port |
| `REDIS_PORT` | `56379` | Redis host port |
| `POSTGRES_PASSWORD` | local-only value | Local database credential |
| `OPENAPI_ENABLED` | `true` | Enables Swagger/OpenAPI |
| `LOG_LEVEL` | `INFO` | Backend logging level |
| `CACHE_TTL_SECONDS` | `300` | Cache lifetime |
| `API_FOOTBALL_KEY` | empty | Optional live-data provider key |

Tests generate ephemeral credentials and ownership state. They do not use
`.env.local`, never load `.env.test`, and cannot target development providers.
Internal container URLs are derived automatically.


Host Flask derives PostgreSQL at `127.0.0.1:POSTGRES_PORT` and Redis at
`127.0.0.1:REDIS_PORT/0`. Docker Flask uses `postgres:5432` and `redis:6379/0`.
Both use database `goal_stats_service_local`, user `goalstats`, the existing password,
and cache namespace `goal-stats-service:local:v1`. `APP_PORT` defaults to 5100 in both.
Direct startup supplies `API_FOOTBALL_KEY` to the provider without logging it.

The file must be a private regular file owned by the user (mode 600 on POSIX), not a
symlink. Use unique, unquoted `KEY=value` lines and whole-line comments. Values are
literal: no whitespace, shell substitutions, interpolation, quotes, or inline comments.
Passwords use letters, digits, underscores, and hyphens; existing credentials are never
rotated. Other values accept letters/digits and `_./:@+-`. Invalid values fail without
being printed. Setup validates existing configuration without rewriting it.

Conflicting inherited ports, credentials, API key, policy, `DATABASE_URL`, `REDIS_URL`,
`APP_ENV`, or `HOST_APP_PORT` are rejected. Remove such exports and use `.env.local`.
No public ENV selector or second persistent environment file exists. Direct Python
startup loads configuration explicitly; imports/factory/test settings remain independent.


## Explicit PostgreSQL TLS and import targets

Factory/CLI/Alembic execution reads an explicit `DATABASE_URL`; it never falls back
to `.env.local`. Direct `python src/main.py` remains the separate local-development
entry point. Cloud jobs must inject credentials via deployment secrets and set
`FLASK_SKIP_DOTENV=1` when using the Flask executable.

The shared URL validator allows only `sslmode`, `sslrootcert`, `sslcert`, and `sslkey`
query parameters. Supported explicit modes are `disable`, `require`, `verify-ca`,
and `verify-full`. Verification modes require an explicit CA; certificate paths must
be absolute POSIX paths for the application container, except `sslrootcert=system`
with `verify-full`. Client certificate and key must be supplied together. Actual file
availability and certificate validity are enforced by libpq at connection time.
Unknown/duplicate parameters, relative paths, host/service overrides and implicit
TLS fallback modes (`allow`/`prefer`) are rejected. Local URLs without TLS query parameters
retain their existing behavior; explicitly requested TLS disables GSS preference so TLS is actually used.

Cloud imports require `verify-full`, which verifies both the certificate chain and
hostname, plus `--confirm-production` and exact expected host/database flags.
This follows [PostgreSQL's TLS guidance](https://www.postgresql.org/docs/current/libpq-ssl.html).
These safeguards are independent of `APP_ENV`, and apply to dry-runs too. SQLAlchemy
hides parameters and CLI errors suppress raw connection/driver messages. Migrations
and imports share `DatabaseSettings` and the same engine construction. The importer
checks schema readiness but never migrates automatically.

See [historical import operations](football.md#historical-import-operations) for local
and cloud one-off commands. No production credentials belong in the repository.

Legacy configuration conversion and host-session discovery are retired. Old secret-file
names remain ignored by Git; they do not authorize a runtime target. `APP_ENV=dev` remains
an explicitly injected application label for compatibility, with no separate DEV lifecycle.
