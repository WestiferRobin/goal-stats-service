# Make interface

Run commands from the repository root, sequentially.

| Command | Contract |
| --- | --- |
| `make setup` | Check Docker/Compose/Make/Python 3.12, preserve/create `.env.local`, prepare `.venv` and images; start nothing |
| `make infra` | Stop owned Docker Flask; start/wait for PostgreSQL and Redis only |
| `make run` | Validate host setup; stop owned Docker Flask; prepare database; run foreground host Flask |
| `make deploy` | Deploy the complete backend locally in Docker. No cloud deployment. |
| `make test` | Run quality checks and owned disposable unit/integration tests |
| `make stop` | Remove local Docker containers/network; preserve PostgreSQL data |
| `make help` | Display these seven commands |

`run` and `deploy` differ in where Flask executes. Both use project
`goalstats-service-local`, database `goal_stats_service_local`, and `.env.local`.
Both build the preparation image and run the same migrations/import before Flask starts.
`infra` does not migrate/import and refuses an occupied application port.

Ctrl-C or IDE Stop ends host Flask; providers remain running. Stop host Flask before
`deploy` or `infra`. `stop` never kills a host process and never deletes the database volume.
If Flask remains running after `stop`, it loses access to its providers.
Private underscore-prefixed maintenance targets remain outside this public interface.
