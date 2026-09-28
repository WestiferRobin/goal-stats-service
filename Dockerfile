FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
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
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=12 \
  CMD python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/ready',timeout=2); assert r.status == 200 and r.read() == b'Healthy'"
CMD ["gunicorn", "--bind=0.0.0.0:8000", "--workers=2", "--timeout=30", "--graceful-timeout=10", "--access-logfile=-", "--error-logfile=-", "main:create_app()"]

FROM runtime AS tooling
COPY tests/ ./tests/
COPY scripts/ ./scripts/
COPY pytest.ini ruff.toml mypy.ini ./
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
