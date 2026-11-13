"""Real libpq TLS verification, using a TLS-only local peer (no database or SQL)."""

import shutil
import socket
import ssl
import struct
import subprocess
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest


@pytest.fixture(scope="module")
def tls_certificate(tmp_path_factory):
    directory = tmp_path_factory.mktemp("tls-peer")
    certificate, key = directory / "ca.pem", directory / "key.pem"
    openssl = shutil.which("openssl")
    assert openssl, "OpenSSL is required for the isolated TLS regression test"
    subprocess.run(
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(certificate),
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost",
        ],
        check=True,
        capture_output=True,
    )
    return certificate, key


@pytest.mark.parametrize("case", ["trusted", "wrong-host", "untrusted", "explicit-ca"])
def test_libpq_verified_tls_uses_configured_ca_store(tls_certificate, tmp_path, monkeypatch, case):
    certificate, key = tls_certificate
    # Isolate OpenSSL from the host trust store. The image sets these same variables
    # to Debian's CA bundle/directories; this test uses an ephemeral private root.
    monkeypatch.setenv(
        "SSL_CERT_FILE", str(certificate if case != "untrusted" else tmp_path / "missing")
    )
    monkeypatch.setenv("SSL_CERT_DIR", str(tmp_path))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate, key)

    with socket.socket() as listener, ThreadPoolExecutor(max_workers=1) as executor:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(5)

        def peer():
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(5)
                assert connection.recv(8) == struct.pack("!II", 8, 80877103)
                connection.sendall(b"S")
                try:
                    with context.wrap_socket(connection, server_side=True) as encrypted:
                        # Successful TLS: stop before PostgreSQL startup/authentication.
                        return encrypted.version()
                except ssl.SSLError:
                    return None

        future = executor.submit(peer)
        with pytest.raises(psycopg.OperationalError) as failure:
            psycopg.connect(
                host="wrong.invalid" if case == "wrong-host" else "localhost",
                hostaddr="127.0.0.1",
                port=listener.getsockname()[1],
                user="tls_test",
                dbname="tls_test",
                password="",
                connect_timeout=3,
                sslmode="verify-full",
                sslrootcert=str(certificate) if case == "explicit-ca" else "system",
                gssencmode="disable",
            )
        message = str(failure.value).lower()
        protocol = future.result(timeout=5)
    if case == "untrusted":
        assert "certificate verify failed" in message
    elif case == "wrong-host":
        assert "does not match host name" in message
    else:
        assert protocol in {"TLSv1.2", "TLSv1.3"}
        assert "certificate" not in message
        assert "server closed the connection" in message or "eof" in message
