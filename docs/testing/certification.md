# Release certification

This is maintainer material, not part of first-run onboarding.

The internal `make _certify` target retains the repository's broader release and
failure-path validation: quality checks, tooling tests, disposable runtime tests,
coverage, smoke tests, lifecycle interruption, resource-ownership checks, and
cleanup assertions. `make _coverage` runs application coverage separately.

Migration authors can use internal `_migration` and `_migration-check` targets and
must review generated Alembic revisions before sharing them. These commands may
require the maintainer Python/tooling environment and intentionally do not appear in
`make help`.

Ordinary contributors should use `make test`.
