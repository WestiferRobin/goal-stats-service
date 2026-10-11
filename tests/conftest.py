"""Shared fixture registration; fixtures own their resource lifetimes."""

pytest_plugins = [
    "tests.fixtures.settings",
    "tests.fixtures.historical",
    "tests.fixtures.application",
    "tests.fixtures.database",
    "tests.fixtures.redis",
    "tests.fixtures.item",
    "tests.fixtures.smoke",
]


def pytest_addoption(parser):
    parser.addoption(
        "--smoke", action="store_true", help="Collect the owned built-system smoke suite"
    )


def pytest_ignore_collect(collection_path, config):
    smoke_root = config.rootpath / "tests" / "smoke"
    if not config.getoption("--smoke") and (
        collection_path == smoke_root or smoke_root in collection_path.parents
    ):
        return True
    return None
