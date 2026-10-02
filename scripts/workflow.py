"""Small Docker workflow shared by Make, smoke, and certification (standard library only)."""

import argparse
import json
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from environment_config import schema
from environment_setup import setup_files

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "goal-stats-service:tooling"
HELP = """GoalStats Flask — host/IDE first; Python 3.12 + Make + running Docker/Compose required.
EVERYDAY  make dev                   Setup, providers, migrate, import CSVs, run host app
          make init                  Same preparation without starting Flask (for IDE users)
          make seed                  Import root data/ CSVs; preserve existing rows
          make quick-test            Fast host unit tests; no Docker required
          make providers-stop        After Ctrl-C: stop providers, keep database data

ADVANCED COMMANDS
SETUP     make setup                 Create/reuse .venv, install pins, prepare private env files
          make doctor                Read-only Python/dependencies/config/Docker/port diagnosis
HOST      make providers             Healthy LOCAL PostgreSQL + Redis; no app/migration
          .venv/bin/python src/main.py  Or IDE Run; requires providers + migrated schema
DATABASE  make migrate               Upgrade schema; starts providers/builds a missing image
          make migration MESSAGE="description"  Generate LOCAL revision; review before use
          make migration-check       Check selected schema/model drift (requires migration)
DOCKER    make build                 Refresh runtime image after source/dependency/schema edits
          make run                   Docker LOCAL app; migrate first (never auto-migrates)
          make logs                  Recent selected-stack logs
TEST      .venv/bin/python -m pytest tests/unit  Fast, Docker-free feedback after setup
          make unit                  Network-disabled container unit suite
          make integration           Owned disposable TEST providers + integration suite
          make test                  Unit + integration once, isolated providers
          make coverage              Full application suite + terminal coverage
          make tooling               Provider-free workflow tests in a container
          make test-providers        Optional foreground owned TEST session for IDE debugging
QUALITY   make check                 Ruff lint/format and strict mypy, no edits
RELEASE   make smoke                 Built disposable DEV HTTP smoke
          make certify-host          Host acceptance; requires setup; no IDE UI claim
          make certify               Quality/tooling/coverage/smoke/lifecycle/failure acceptance
SHUTDOWN  make providers-stop        Stop LOCAL providers only; preserve database data
          make stop                  Remove selected Docker containers/network; preserve DB
Default ENV=local. Docker/database commands also accept ENV=dev; providers are LOCAL only.
Start Docker Desktop, then make dev. IDE users: make init, then IDE Run.
Dev/init apply LOCAL migrations and import CSVs explicitly before starting the app.
TEST is automatic. Release checks are heavier. No command stages, commits or publishes.
"""


def run(args, *, capture=False, env=None, check=True):
    """Terminate/reap the CLI child before outer resource cleanup on interruption."""
    process = subprocess.Popen(
        [str(a) for a in args],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True,
    )
    try:
        stdout, stderr = process.communicate()
    except BaseException:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        raise
    if check and process.returncode:
        # Do not print Compose config/command arguments, which can contain credentials.
        if capture and stderr:
            print(stderr, file=sys.stderr)
        raise subprocess.CalledProcessError(process.returncode, args[0])
    return subprocess.CompletedProcess(args[0], process.returncode, stdout, stderr)


def interrupted(signum, _frame):
    raise SystemExit(128 + signum)


def install_signals():
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)


def setup(directory=ROOT):
    from python_environment import bootstrap

    bootstrap(Path(directory))
    for tool in ("docker", "make"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"Required tool missing: {tool}")
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Python 3.12 is required for host orchestration and the application")
    run(["docker", "compose", "version"])
    run(["docker", "info"], capture=True)

    def has_volume(mode):
        label = "label=com.docker.compose.project=" + schema.SERVICE + "-" + mode
        return bool(
            run(["docker", "volume", "ls", "-q", "--filter", label], capture=True).stdout.strip()
        )

    def verify(mode, values):
        selected = {
            **values,
            "POSTGRES_PASSWORD": values[
                "POSTGRES_PASSWORD" if mode == "local" else "DEV_POSTGRES_PASSWORD"
            ],
            "APP_PORT": values[mode.upper() + "_APP_PORT"],
        }
        stack = Stack(mode, settings=selected)
        if stack.compose("ps", "--status", "running", "-q", "app", capture=True).stdout.strip():
            raise RuntimeError("Stop the full app before migrating private configuration.")
        existed = bool(stack.compose("ps", "-a", "-q", "postgres", capture=True).stdout.strip())
        was_running = bool(
            stack.compose(
                "ps", "--status", "running", "-q", "postgres", capture=True
            ).stdout.strip()
        )
        try:
            stack.compose("up", "-d", "--wait", "--wait-timeout", "60", "postgres")
            result = stack.compose(
                "exec",
                "-T",
                "-e",
                "PGPASSWORD=" + selected["POSTGRES_PASSWORD"],
                "postgres",
                "psql",
                "-h",
                "postgres",
                "-U",
                "goalstats",
                "-d",
                schema.DATABASE + "_" + mode,
                "-At",
                "-c",
                "SELECT 1",
                capture=True,
                check=False,
            )
            if result.returncode or result.stdout.strip() != "1":
                raise RuntimeError(
                    "Existing PostgreSQL authentication failed; configuration preserved."
                )
        finally:
            if not was_running:
                stack.compose("stop", "postgres")
                if not existed:
                    stack.compose("rm", "-f", "postgres")

    setup_files(directory, has_volume=has_volume, verify=verify)
    print("Setup ready. Use make dev to prepare the database and start the app.")


def read_settings(path, mode="local"):
    try:
        values = schema.load_machine(path)
    except schema.ConfigurationError as exc:
        raise RuntimeError(str(exc)) from None
    return {
        **values,
        "POSTGRES_PASSWORD": values[
            "POSTGRES_PASSWORD" if mode == "local" else "DEV_POSTGRES_PASSWORD"
        ],
        "APP_PORT": values[mode.upper() + "_APP_PORT"],
    }


class Stack:
    def __init__(self, env, *, project=None, settings=None):
        if env not in {"local", "dev", "test"}:
            raise RuntimeError("ENV must be local or dev (TEST is managed automatically)")
        self.env = env
        self.project = project or f"goal-stats-service-{env}"
        self.disposable = project is not None
        if self.disposable and not re.fullmatch(
            r"goal-stats-service-(test|cert)-[a-f0-9]+", project
        ):
            raise RuntimeError("Disposable project must use a unique owned test/cert identity")
        self.settings = (
            settings if settings is not None else read_settings(ROOT / ".env.local", env)
        )
        # Ignore ambient application/Compose settings, and never source shell env files.
        self.process_env = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSE_")}
        self.process_env.update(
            schema.test_policy(ROOT) if env == "test" else schema.POLICY_DEFAULTS
        )
        self.process_env.update(self.settings)
        # Optional LOCAL settings must never come from ambient shell variables.
        for key, default in (("LOCAL_POSTGRES_PORT", "55432"), ("LOCAL_REDIS_PORT", "56379")):
            self.process_env[key] = self.settings.get(key, default)
        self.args = [
            "docker",
            "compose",
            "--env-file",
            os.devnull,
            "-p",
            self.project,
            "-f",
            ROOT / "docker" / f"compose.{env}.yml",
        ]
        self.service = "runner" if env == "test" else "app"

    def compose(self, *args, **kwargs):
        return run([*self.args, *args], env=self.process_env, **kwargs)

    def providers(self):
        self.compose("up", "-d", "--wait", "--wait-timeout", "60", "postgres", "redis")

    def command(self, *args, options=(), **kwargs):
        name = self.project + "-oneoff-" + secrets.token_hex(6)
        try:
            with tempfile.TemporaryDirectory() as directory:
                compose_options = ()
                if self.env == "test":
                    receipt = Path(directory) / "owned-test.json"
                    receipt.write_text(
                        json.dumps(
                            {
                                "hostname": name,
                                "TEST_DATABASE_URL": "postgresql+psycopg://goalstats:"
                                + self.settings["POSTGRES_PASSWORD"]
                                + "@postgres:5432/goalstats_test_runtime",
                                "TEST_REDIS_URL": "redis://redis:6379/0",
                            }
                        )
                    )
                    # The enclosing directory is 0700; the non-root runner reads the mount.
                    receipt.chmod(0o444)
                    override = Path(directory) / "runner.json"
                    override.write_text(
                        json.dumps(
                            {
                                "services": {
                                    "runner": {
                                        "hostname": name,
                                        "volumes": [f"{receipt}:/run/owned-test.json:ro"],
                                    }
                                }
                            }
                        )
                    )
                    compose_options = ("-f", override)
                return run(
                    [
                        *self.args,
                        *compose_options,
                        "run",
                        "--rm",
                        "--no-deps",
                        "-T",
                        "--name",
                        name,
                        *options,
                        self.service,
                        *args,
                    ],
                    env=self.process_env,
                    **kwargs,
                )
        finally:
            run(["docker", "rm", "-f", name], capture=True, check=False)

    def migrate(self):
        self.providers()
        self.command("alembic", "upgrade", "head")

    def start(self):
        self.compose("up", "-d", "--wait", "--wait-timeout", "90", "app")
        wait_ready(self.url)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.settings['APP_PORT']}"

    def stop(self, *, volumes=False):
        if volumes and not self.disposable:
            raise RuntimeError("Refusing removal of persistent developer volumes")
        # A second signal must not interrupt resource cleanup.
        old = {s: signal.signal(s, signal.SIG_IGN) for s in (signal.SIGTERM, signal.SIGINT)}
        try:
            self.compose(
                "down", "--remove-orphans", "--timeout", "15", *(["--volumes"] if volumes else [])
            )
        finally:
            for sig, handler in old.items():
                signal.signal(sig, handler)


def inventory():
    return {
        kind: set(run(command, capture=True).stdout.splitlines())
        for kind, command in {
            "containers": ["docker", "ps", "-aq", "--no-trunc"],
            "images": ["docker", "image", "ls", "-a", "-q", "--no-trunc"],
            "networks": ["docker", "network", "ls", "-q", "--no-trunc"],
            "volumes": ["docker", "volume", "ls", "-q"],
        }.items()
    }


def assert_absent(project):
    label = "label=com.docker.compose.project=" + project
    for command in (
        ["docker", "ps", "-aq", "--filter", label],
        ["docker", "network", "ls", "-q", "--filter", label],
        ["docker", "volume", "ls", "-q", "--filter", label],
    ):
        assert not run(command, capture=True).stdout.strip(), f"Leaked resource in {project}"


def fresh(env):
    # Port allocation is checked by Docker at startup; a competing bind fails safely.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return Stack(
        env,
        project="goal-stats-service-cert-" + secrets.token_hex(6),
        settings={
            "POSTGRES_PASSWORD": secrets.token_hex(24),
            "APP_PORT": str(port),
            "LOCAL_POSTGRES_PORT": "0",
            "LOCAL_REDIS_PORT": "0",
        },
    )


def wait_ready(url, timeout=45):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            with urllib.request.urlopen(url + "/ready", timeout=2) as response:
                if response.status == 200 and response.read() == b"Healthy":
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.25)
    raise RuntimeError("Startup requires HTTP 200 and exact Healthy; readiness timed out")


def build_tooling():
    run(["docker", "build", "--target", "tooling", "-t", IMAGE, "."])


def tool_command(*command):
    name = "goal-stats-service-tool-" + secrets.token_hex(6)
    try:
        run(["docker", "run", "--rm", "--name", name, "--network", "none", IMAGE, *command])
    finally:
        run(["docker", "rm", "-f", name], capture=True, check=False)


def tests(mode, *, fault=None, project=None):
    build_tooling()
    if mode in {"unit", "tooling"}:
        target = "tests/unit" if mode == "unit" else "scripts/tests"
        tool_command("pytest", "-q", "-p", "no:cacheprovider", target)
        return
    stack = Stack(
        "test",
        project=project or "goal-stats-service-test-" + secrets.token_hex(6),
        settings={"POSTGRES_PASSWORD": secrets.token_hex(24)},
    )
    try:
        if fault == "provider":
            # Real failed provider startup under the same finally/ownership boundary.
            with tempfile.TemporaryDirectory() as directory:
                override = Path(directory) / "failure.yml"
                override.write_text('services:\n  postgres:\n    command: ["false"]\n')
                stack.args += ["-f", override]
                try:
                    stack.providers()
                finally:
                    stack.args = stack.args[:-2]
        else:
            stack.providers()
        stack.command("alembic", "upgrade", "missing_revision" if fault == "migration" else "head")
        if fault == "signal":
            print("SIGNAL_TEST_RUNNING", flush=True)
            stack.command("python", "-c", "import time; time.sleep(300)")
        targets = (
            ["tests/integration"] if mode == "integration" else ["tests/unit", "tests/integration"]
        )
        command = ["pytest", "-q", "-p", "no:cacheprovider", *targets]
        if fault in {"unit", "integration"}:
            command = ["pytest", "-q", "-p", "no:cacheprovider", "tests/" + fault]
            command += ["-o", "required_plugins=goalstats_deliberately_missing_plugin"]
        if mode == "coverage":
            command += ["--cov=src", "--cov-report=term-missing"]
        stack.command(*command)
    finally:
        stack.stop(volumes=True)


def check():
    build_tooling()
    tool_command("ruff", "check", "--no-cache", ".")
    tool_command("ruff", "format", "--check", "--no-cache", ".")
    tool_command("mypy", "--cache-dir=/tmp/mypy-cache")


def doctor():
    """Read-only prerequisites and private configuration validation."""
    from python_environment import verify

    verify(ROOT)
    interpreter = shutil.which("python3.12")
    if interpreter is None and sys.version_info[:2] == (3, 12):
        interpreter = sys.executable
    if interpreter is None:
        raise RuntimeError("Python 3.12 is unavailable; install it before setup")
    run([interpreter, "--version"])
    for tool in ("docker", "make"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"Required tool missing: {tool}")
    run(["docker", "compose", "version"])
    run(["docker", "info"], capture=True)
    for name in (
        "requirements.txt",
        "Dockerfile",
        "Makefile",
        "alembic.ini",
        "alembic/env.py",
        "docker/compose.local.yml",
        "docker/compose.dev.yml",
        "docker/compose.test.yml",
    ):
        if not (ROOT / name).is_file():
            raise RuntimeError(f"Required repository file missing: {name}")
    for env in ("local", "dev"):
        read_settings(ROOT / ".env.local", env)
        print(f"OK {env.upper()} private configuration")
    schema.read_private(ROOT / ".env.test", frozenset(schema.POLICY_DEFAULTS))
    schema.test_policy(ROOT)
    print("OK TEST policy (no provider endpoints)")
    from diagnostics import check_ports

    check_ports(ROOT)
    print("Doctor: PASS (read-only)")


def local_workflow(command):
    """One LOCAL workflow using the checked-in host code, not a stale Docker image."""
    from python_environment import verify

    if command in {"dev", "init"}:
        setup()
    else:
        verify(ROOT)
    interpreter = ROOT / ".venv/bin/python"
    if command == "quick-test":
        run([interpreter, "-m", "pytest", "tests/unit", "-q"])
        return

    from host_development import local_providers

    stack = Stack("local")
    # Use the same configured LOCAL database for providers, migrations, import and app.
    environment = {k: v for k, v in os.environ.items() if k not in schema.DIRECT_KEYS}
    environment.update(schema.application(stack.settings, "local", host=True))
    environment["PYTHONPATH"] = str(ROOT / "src")
    if command == "seed":
        run([interpreter, "-m", "football.import_data"], env=environment)
        return
    local_providers(stack)
    run([interpreter, ROOT / "scripts/prepare_local_database.py"], env=environment)
    url = f"http://127.0.0.1:{environment['HOST_APP_PORT']}/swagger"
    if command == "init":
        print(f"LOCAL prepared. Run src/main.py in your IDE; Swagger: {url}")
    else:
        print(f"Starting LOCAL: {url}\nStop with Ctrl-C; then make providers-stop.", flush=True)
        run([interpreter, ROOT / "src/main.py"], env=environment)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command")
    parser.add_argument("--env", default=os.environ.get("ENV", "local"), choices=("local", "dev"))
    args = parser.parse_args()
    if args.env not in {"local", "dev"}:
        parser.error("ENV must be local or dev")
    install_signals()
    command = args.command
    if command == "help":
        print(HELP)
    elif command in {"dev", "init", "seed", "quick-test"}:
        if args.env != "local":
            raise RuntimeError(f"make {command} requires ENV=local")
        local_workflow(command)
    elif command == "setup":
        setup()
    elif command == "doctor":
        doctor()
    elif command in {"providers", "providers-stop"}:
        if args.env != "local":
            raise RuntimeError("Host providers require ENV=local")
        from host_development import local_providers

        local_providers(Stack("local"), stop=command == "providers-stop")
    elif command == "test-providers":
        from host_development import test_providers

        test_providers()
    elif command in {"unit", "integration", "test", "coverage", "tooling"}:
        tests(command)
    elif command == "check":
        check()
    elif command == "smoke":
        from smoke.runtime import smoke

        smoke()
    elif command == "certify":
        from validation.certify_workflows import certify

        certify()
    elif command == "certify-host":
        from validation.certify_host import certify_host

        certify_host()
    elif command in {"build", "migrate", "run", "stop", "logs", "migration", "migration-check"}:
        if command == "migration" and (
            args.env != "local" or not os.environ.get("MESSAGE", "").strip()
        ):
            raise RuntimeError('Migration creation requires ENV=local and nonempty MESSAGE="..."')
        stack = Stack(args.env)
        if command == "build":
            stack.compose("build", "app")
        elif command == "migrate":
            stack.migrate()
        elif command == "run":
            stack.start()
            print(f"{args.env.upper()} ready: {stack.url}/swagger")
        elif command == "stop":
            stack.stop()
        elif command == "logs":
            stack.compose("logs", "--tail", "100")
        elif command == "migration-check":
            stack.providers()
            stack.command("alembic", "check")
        else:
            stack.providers()
            stack.command(
                "alembic",
                "revision",
                "--autogenerate",
                "-m",
                os.environ["MESSAGE"],
                options=(
                    "--user",
                    f"{os.getuid()}:{os.getgid()}",
                    "-v",
                    f"{ROOT / 'alembic'}:/app/alembic",
                ),
            )
    else:
        parser.error("Unknown command")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, schema.ConfigurationError, subprocess.CalledProcessError) as exc:
        print(f"Workflow failed: {exc}", file=sys.stderr)
        sys.exit(exc.returncode if isinstance(exc, subprocess.CalledProcessError) else 1)
