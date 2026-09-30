# GoalStats documentation

New teammate? Start with the [README setup guide](../README.md#run-locally), then
[verify your first Swagger request](../README.md#verify-your-first-run).
The usual command is `make dev`; IDE users run `make init` before Run/Debug.

| You need to… | Read |
| --- | --- |
| Find commands or understand their effects | [Make interface](interface/make.md) |
| Set up an IDE or understand host/Docker differences | [Developer workflow](service/development.md) |
| Use predictions, CSVs, live refresh or backtests | [Football API and data](service/football.md) |
| Use SQL instead of the migration/import tools | [SQL scripts](../sql/README.md) |
| Understand configuration, ports and credentials | [Environment](service/environment.md) |
| Understand the backend structure | [Architecture](service/architecture.md) |
| Choose tests or debug integration tests | [Test ownership](testing/overview.md) |
| Verify a built application | [Smoke checks](testing/smoke.md) |
| Maintain CI and release checks | [Certification](testing/certification.md) |
| Understand remaining template names | [Repository identity](standard/template.md) |

This is one backend application. The remaining `template` names identify existing
Docker projects, databases and tooling; new contributors do not scaffold a service.
