# HTTP testing scope

`make test` is the supported verification command. Flask integration tests cover the
application API using disposable providers, including catalog browsing, Scenario CRUD,
saved Predictions, history, error responses and OpenAPI.

The older real-HTTP tests under `tests/smoke` remain as reference coverage, excluded
from pytest collection. Their dedicated runner, synthetic-data preparation and disposable
app profile are retired. They are not automatically run and have no supported Make or
shell mode. Do not point these state-changing fixtures at development providers.

For a manual local availability check after `make run` or `make deploy`, inspect
`/health`, `/ready` and `/swagger`. Use disposable databases for state-changing acceptance
checks; do not create persistent records merely to validate the development workflow.
