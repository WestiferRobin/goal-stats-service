FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
# psycopg-binary ships OpenSSL with trust paths outside Debian's CA store.
# sslrootcert=system must use the same maintained bundle as the system TLS client.
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt SSL_CERT_DIR=/etc/ssl/certs
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --no-deps -r requirements.txt \
    && python -m pip check \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app
COPY src/ ./src/
COPY data/ ./data/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY sql/ ./sql/
COPY scripts/deployment/start.sh ./scripts/deployment/start.sh
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=12 \
  CMD python -c "import os, urllib.request; r=urllib.request.urlopen('http://127.0.0.1:'+(os.environ.get('PORT') or '8000')+'/ready',timeout=2); assert r.status == 200"
CMD ["/bin/sh", "/app/scripts/deployment/start.sh"]

FROM runtime AS tooling
COPY tests/ ./tests/
COPY scripts/ ./scripts/
COPY .coveragerc pytest.ini ruff.toml mypy.ini Makefile .env.example ./
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

FROM runtime AS historical_source
# Fetch only the immutable approved CSV; never package the developer's data/raw directory.
RUN python -c "import hashlib,json; from pathlib import Path; from urllib.request import urlopen; m=json.loads(Path('data/womens-world-cup/womens-world-cup-2023.json').read_text()); url='https://raw.githubusercontent.com/martj42/womens-international-results/'+m['upstream_revision']+'/results.csv'; data=urlopen(url,timeout=60).read(); assert hashlib.sha256(data).hexdigest()==m['sha256'], 'Pinned historical source checksum mismatch'; Path('/tmp/results.csv').write_bytes(data)"

FROM runtime AS production
COPY --from=historical_source /tmp/results.csv /app/data/bootstrap/results.csv
