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
`.env.local`, do not require `.env.test`, and cannot target development providers.
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
