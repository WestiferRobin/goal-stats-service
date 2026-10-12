"""Shared fixture registration; fixtures own their resource lifetimes."""

pytest_plugins = [
    "tests.fixtures.settings",
    "tests.fixtures.historical",
    "tests.fixtures.application",
    "tests.fixtures.database",
    "tests.fixtures.redis",
    "tests.fixtures.item",
    "tests.fixtures.smoke",
    "tests.fixtures.workflow",
    "tests.fixtures.scenarios",
]


def pytest_ignore_collect(collection_path, config):
    # Retained HTTP reference tests have no supported launcher or fixture setup.
    smoke_root = config.rootpath / "tests" / "smoke"
    if collection_path == smoke_root or smoke_root in collection_path.parents:
        return True
    return None
