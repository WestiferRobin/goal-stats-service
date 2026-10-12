# Workflow verification

`make test` is the standard automated verification command. It runs quality checks,
unit/integration tests and relevant tooling/resource-ownership tests. There is no
separate lifecycle certification command or failure-injection runner.

The normal test runner validates disposable provider ownership before migrations and
fixtures, cleans its own project on completion/failure/signals, and verifies preservation
of preexisting resources. Focused shell tests cover failure propagation and SIGINT/SIGTERM
cleanup with recording executables; unit tests reject unsafe targets and malformed receipts.

For a separately requested manual lifecycle audit, record database digests and resource
identities first, verify the eight public commands sequentially (use `DRY=true` for seed unless writes are explicitly authorized), verify readiness and data
preservation, and restore the original running state. Never reset development PostgreSQL,
remove persistent volumes, or signal arbitrary processes to force a passing result.

Dated backend certification reports describe historical executions. They are retained
as evidence and do not define additional supported commands.
