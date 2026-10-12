# Make interface

Run commands from the repository root, sequentially.

| Command | Contract |
| --- | --- |
| `make setup` | Check Docker/Compose/Make/Python 3.12, preserve/create `.env.local`, prepare `.venv` and images; start nothing |
| `make infra` | Stop owned Docker Flask; start/wait for PostgreSQL and Redis only |
| `make run` | Validate host setup; stop owned Docker Flask; prepare database; run foreground host Flask |
| `make deploy` | Deploy the complete backend locally in Docker. No cloud deployment. |
| `make seed DATASET=… DRY=true` | Preview approved historical imports; omit DRY or use false to write. |
| `make test` | Run quality checks and owned disposable unit/integration tests |
| `make stop` | Remove local Docker containers/network; preserve PostgreSQL data |
| `make help` | Display these eight commands |

`run` and `deploy` differ in where Flask executes. Both use project
`goalstats-service-local`, database `goal_stats_service_local`, and `.env.local`.
Both build the preparation image and run the same migrations before Flask starts.
`infra` does not migrate/import and refuses an occupied application port.

Ctrl-C or IDE Stop ends host Flask; providers remain running. Stop host Flask before
`deploy` or `infra`. `stop` never kills a host process and never deletes the database volume.
If Flask remains running after `stop`, it loses access to its providers.
These are the only supported Make commands. `make test` is the standard verification
command and runs quality checks plus unit, integration and maintained tooling tests
using owned disposable PostgreSQL/Redis. There are no separate test modes.

Alembic and all existing revisions remain in place. Startup applies existing revisions;
future migration generation must be planned and explicitly authorized separately.
Historical dataset imports remain explicit operations described in the football guide.


## Startup and empty databases

Startup prepares the schema with Alembic but never seeds prototype or historical data.
Existing populated databases retain their records. Fresh databases have empty application
catalogs while health, readiness and Swagger remain available. Prototype compatibility
endpoints may return empty collections or missing-team errors. The existing `/demo` and
frontend demo require explicitly supplied prototype data or migration to normalized
Goal Stats APIs; startup does not fabricate ratings or historical examples for them.

The explicit prototype compatibility importer remains available. Historical imports use
the guarded Flask CLI described in the [football guide](../service/football.md#historical-import-operations).
Use the explicit `make seed` workflow described below to import approved historical data.

## Explicit historical seeding

```bash
make seed DATASET=womens-world-cup DRY=true
make seed DATASET=womens-world-cup DRY=false
make seed DATASET=womens-world-cup-2023 DRY=false
```

`womens-world-cup` expands to 1991, 1995, 1999, 2003, 2007, 2011, 2015, 2019 and
2023, in that order. Each individual `womens-world-cup-YYYY` ID is also accepted.
The nine contracts remain in `data/womens-world-cup/`; there is no group manifest.
`DATASET` is required. `DRY` accepts only lowercase `true` or `false`, defaults to
`false` only when omitted, and rejects an empty value. Legacy `DRY_RUN` is rejected.

Prepare the runtime image, providers and current Alembic schema separately using the
existing setup/startup workflow. Supply the pinned `results.csv` under
`data/raw/martj42-womens-results/1855e313ae8bcd0330426e62c8e4cf15ce45077c/`.
Seed checks prepared-image compatibility and mounts only that input directory read-only.
It never builds/pulls images, starts dependencies, applies migrations or resets data.
It uses canonical local configuration and verifies the connected PostgreSQL identity
and Alembic revision through the existing importer. Unsupported Compose overrides fail.

Each edition has its own transaction. On failure, earlier confirmed commits remain,
the current edition is reported as failed and later editions are not attempted.
A lost commit acknowledgment may be unconfirmed; review the error, preview again and
retry the same command. Identical reimports insert no duplicate records or overwrite facts.
The group is not globally atomic. Successful writes report confirmed inserted totals.

`DRY=true` uses PostgreSQL-enforced read-only transactions. Each edition reports its own
estimates and snapshot; shared-team estimates are not summed into a group total.
Complete approved coverage is 44 historical teams, nine competitions and 348 matches.
The implementation itself does not populate development PostgreSQL: its existing
2023 catalog remains until an explicit write-mode operation is authorized and executed.

Startup never imports datasets. Seed never selects `data/prototype/`, supplies prototype
ratings or invents fields; RoadToTheFinal compatibility operations remain separate.
