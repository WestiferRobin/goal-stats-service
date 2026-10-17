"""Shared fixture registration; fixtures own their resource lifetimes."""

pytest_plugins = [
    "tests.fixtures.settings",
    "tests.fixtures.historical",
    "tests.fixtures.historical_database",
    "tests.fixtures.application",
    "tests.fixtures.database",
    "tests.fixtures.redis",
    "tests.fixtures.workflow",
    "tests.fixtures.scenarios",
]
