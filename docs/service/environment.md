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
