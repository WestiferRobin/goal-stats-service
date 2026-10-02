# Built-system smoke testing

This is maintainer material, not part of first-run onboarding.

The internal `make _smoke` target builds a production-style Gunicorn application
and tests it through HTTP in uniquely named disposable Docker resources. It checks
liveness, readiness, OpenAPI, representative Item/Action behavior, persistence,
cache behavior, and safe cleanup. It does not use the Flask test client or the
developer's local database.

Ordinary contributors should use `make test`.
