"""Host CLI: python -m football.import_data [directory]."""

import argparse
from pathlib import Path

from football.datasets import DATA_DIRECTORY, import_datasets
from infra.resources.db import Database
from settings.environment import load_local


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=DATA_DIRECTORY)
    args = parser.parse_args()
    database = Database(load_local().database)
    try:
        with database.transaction() as session:
            print(import_datasets(session, args.directory))
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
