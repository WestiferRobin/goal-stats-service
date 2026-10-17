"""Real driver identity checks on ownership-verified disposable PostgreSQL only."""

import socket

import pytest
from sqlalchemy import event, text

from football.bootstrap import BootstrapDiagnostic, FailureCategory
from infra.resources.db import Database, verify_database_identity
from settings.base import ConfigurationError
from settings.database import DatabaseSettings, ImportTarget, database_url

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("case", ["valid", "host", "database", "user"])
def test_real_driver_identity(postgres_config, case):
    actual = database_url(postgres_config["DATABASE_URL"])
    # Use a DNS name resolving to the same disposable loopback provider. The
    # application check must compare this name, not the resolved address.
    configured = actual.set(host="localhost")
    if case == "database":
        configured = configured.set(database=actual.database + "_unexpected")
    address = socket.gethostbyname(actual.host)
    database = Database(DatabaseSettings(configured))
    target = ImportTarget("test", configured.host, configured.database)

    @event.listens_for(database.engine, "do_connect")
    def connect_to_disposable(dialect, record, args, params):
        # Deliberately separate actual connection identity from engine metadata
        # for negative tests. No connection ever leaves the owned test provider.
        params["hostaddr"] = address
        if case == "host":
            params["host"] = "unexpected.invalid"
        if case == "database":
            params["dbname"] = actual.database

    expected = {
        "host": FailureCategory.CONNECTED_HOST,
        "database": FailureCategory.CONNECTED_DATABASE,
        "user": FailureCategory.CONNECTED_USER,
    }
    try:
        with database.transaction() as session:
            driver = session.connection().connection.driver_connection
            if case == "valid":
                assert driver.info.host == "localhost"
                assert driver.info.hostaddr == address
                assert driver.info.host != driver.info.hostaddr
                verify_database_identity(session, target)
            else:
                if case == "user":
                    session.execute(text("SET LOCAL ROLE pg_read_all_data"))
                with pytest.raises(ConfigurationError) as failure:
                    verify_database_identity(session, target)
                assert BootstrapDiagnostic().category(failure.value) == expected[case]
    finally:
        database.dispose()
