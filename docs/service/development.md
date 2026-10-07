# Backend development

`make run` runs host Flask with Docker PostgreSQL/Redis.
`make deploy` runs Flask and both providers in Docker, locally only.
Both use one `.env.local`, one database, the same migrations and football data.

## Preparation

Use Python 3.12, GNU Make, and running Docker/Compose v2 on macOS, Linux, or WSL.
Native Windows host Python is not supported; use WSL. Run `make setup` to create/reuse
`.venv`, install pinned requirements when needed, run `pip check`, and prepare images.
Setup never starts services or overwrites `.env.local`. A wrong-version venv is refused;
move it aside yourself before retrying. Setup does not install Python itself.

## Coding and debugging

Run `make run`. It validates host prerequisites before stopping Docker Flask, checks
`APP_PORT`, builds the preparation image, starts healthy providers, migrates/imports,
and executes `.venv/bin/python src/main.py` in the foreground. Ctrl-C ends only Flask.
Restart manually after edits; host reload and the browser debugger are disabled.

VS Code's app launch configuration already selects `.venv/bin/python` and `src/main.py`.
For PyCharm or another debugger, use that interpreter/script and the repository root as
working directory. Breakpoints work in the single host process. Do not configure a second
env file. To prepare the database for initial IDE use or after migrations change, run
`make run`, stop Flask, then IDE Run. For a prepared database, use `make infra` then IDE Run.
The retained IDE test-session configuration is private tooling; use `make test` for checks.

## Switching and stopping

- Docker to host: `make run` stops only this project's Docker app and reuses providers.
- Host to Docker: Ctrl-C/IDE Stop, then `make deploy`.
- Infrastructure only: stop host Flask, then `make infra`; Docker Flask is stopped automatically.
- Finished: stop host Flask, then `make stop`. PostgreSQL's named volume remains.

Occupied ports produce an error; no arbitrary process is killed. Commands must run
sequentially. `make stop` does not manage host processes; any remaining host Flask loses
its database/cache connections. Redis is intentionally ephemeral; PostgreSQL persists.

## Internal ownership

`scripts/local.sh` owns the public lifecycle and fixed project `goalstats-service-local`.
Its shared preparation function uses one-off Docker app commands for Alembic and football
import. Application startup itself never migrates/imports. Host configuration is explicit
in `load_local`; ordinary factory calls and tests never load `.env.local` automatically.

Retained `workflow.py`, DEV Compose, and certification helpers are private legacy tooling.
They are not used by the public runtime actions. Do not invoke their old local lifecycle:
it has a different project identity. Cleanup/migration of those private dependencies is
separate work. Existing underscore-prefixed maintenance targets remain private.
