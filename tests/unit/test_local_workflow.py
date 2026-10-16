"""Public local lifecycle tests against recording executables."""

from pathlib import Path

import pytest

from football.historical_dataset import APPROVED_DATASETS

ROOT = Path(__file__).resolve().parents[2]


def commands(calls):
    return [" ".join(call) for call in calls]


def test_help_has_exact_public_contract(workflow):
    run, _ = workflow
    result, calls = run("help")
    assert result.returncode == 0
    for name in ("setup", "infra", "run", "deploy", "seed", "test", "certify", "stop", "help"):
        assert "make " + name in result.stdout
    assert "No cloud deployment" in result.stdout
    assert calls == []
    assert "make providers" not in result.stdout


def test_setup_preserves_file_and_starts_nothing(workflow):
    run, root = workflow
    before = (root / ".env.local").read_bytes()
    result, calls = run("setup")
    assert result.returncode == 0, result.stderr
    assert (root / ".env.local").read_bytes() == before
    events = commands(calls)
    assert "python3.12 scripts/development/python_environment.py bootstrap" in events
    assert any("build --target tooling" in call for call in events)
    assert not any(" up " in call or " run " in call or " stop " in call for call in events)


def test_setup_creates_missing_file(workflow):
    run, root = workflow
    (root / ".env.local").unlink()
    result, _ = run("setup")
    assert result.returncode == 0
    assert (root / ".env.local").read_bytes() == (root / ".env.example").read_bytes()
    assert (root / ".env.local").stat().st_mode & 0o777 == 0o600


def test_infra_stops_only_owned_app_and_starts_only_providers(workflow):
    run, _ = workflow
    result, calls = run("infra")
    assert result.returncode == 0
    docker = [c for c in calls if c[0] == "docker" and c[1:3] == ["compose", "--env-file"]]
    assert all(
        c[2:8]
        == [
            "--env-file",
            ".env.local",
            "-p",
            "goalstats-service-local",
            "-f",
            "docker/compose.local.yml",
        ]
        for c in docker
    )
    assert [c[8:] for c in docker] == [
        ["config", "--quiet"],
        ["stop", "app"],
        ["up", "-d", "--wait", "--wait-timeout", "90", "postgres", "redis"],
    ]


@pytest.mark.parametrize("action", ["run", "deploy"])
def test_preparation_precedes_flask(workflow, action):
    run, _ = workflow
    result, calls = run(action)
    assert result.returncode == 0, result.stderr
    events = commands(calls)
    migration = next(i for i, c in enumerate(events) if c.endswith("alembic upgrade head"))
    providers = next(i for i, c in enumerate(events) if c.endswith("90 postgres redis"))
    assert providers < migration < len(events) - 1
    assert not any("import-football" in c for c in events)
    if action == "run":
        assert calls[-1] == ["python", "src/main.py"]
        assert events.index("python3.12 scripts/development/python_environment.py verify") < next(
            i for i, c in enumerate(events) if c.endswith("stop app")
        )
    else:
        assert events[-1].endswith("up -d --wait --wait-timeout 90 app")
        assert not any(c.endswith("stop app") for c in events)


def test_repeated_deploy_allows_owned_listener(workflow):
    run, _ = workflow
    result, calls = run("deploy", APP_RUNNING="1")
    assert result.returncode == 0
    assert ["python3.12", "scripts/development/python_environment.py", "port"] not in calls


@pytest.mark.parametrize("action", ["run", "deploy", "infra"])
def test_port_failure_prevents_build_and_start(workflow, action):
    run, _ = workflow
    result, calls = run(action, FAIL="python_environment.py port")
    assert result.returncode != 0
    assert not any(" up " in c or " build " in c for c in commands(calls))


@pytest.mark.parametrize(
    "failure",
    [
        "python_environment.py config",
        "python_environment.py verify",
        "alembic upgrade head",
        "90 postgres redis",
    ],
)
def test_run_failure_never_launches_host(workflow, failure):
    run, _ = workflow
    result, calls = run("run", FAIL=failure)
    assert result.returncode != 0
    assert ["python", "src/main.py"] not in calls
    if "python_environment.py" in failure:
        assert not any(c.endswith("stop app") for c in commands(calls))
    if "alembic" in failure:
        assert not any(c.endswith("import-football") for c in commands(calls))


def test_stop_preserves_volume_and_does_not_kill_host(workflow):
    run, _ = workflow
    result, calls = run("stop")
    assert result.returncode == 0
    assert "Ctrl-C or IDE Stop" in result.stdout
    assert commands(calls)[-1].endswith("down --remove-orphans")
    assert not any("--volumes" in c or "kill" in c for c in commands(calls))


def test_make_dispatch_keeps_test_independent():
    content = (ROOT / "Makefile").read_text()
    assert "setup infra run deploy stop:" in content
    assert "scripts/development/local.sh $@" in content
    assert "test:\n\t@$(BASH) scripts/testing/test.sh" in content
    assert "certify:\n\t@$(BASH) scripts/testing/test.sh certify" in content
    assert "help:\n\t@$(BASH) scripts/development/local.sh help" in content
    assert ".PHONY: setup infra run deploy seed test certify stop help" in content


def test_gnu_make_version_check_does_not_close_pipe_early(workflow):
    run, _ = workflow
    result, _ = run("infra", LARGE_MAKE_VERSION="1")
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("action", ["setup", "infra", "run", "deploy", "stop"])
def test_invalid_configuration_prevents_mutation(workflow, action):
    run, _ = workflow
    result, calls = run(action, FAIL="python_environment.py config")
    assert result.returncode != 0
    assert not any(word in c for c in calls for word in ("up", "down", "run", "stop", "build"))


def test_stop_does_not_require_free_application_port(workflow):
    run, _ = workflow
    result, calls = run("stop")
    assert result.returncode == 0
    assert ["python3.12", "scripts/development/python_environment.py", "port"] not in calls


@pytest.mark.parametrize("action", ["setup", "infra", "run", "deploy"])
def test_lifecycle_never_imports_datasets(workflow, action):
    run, _ = workflow
    result, calls = run(action)
    assert result.returncode == 0, result.stderr
    assert not any("import-football" in c for c in commands(calls))
    assert "Importing bundled" not in result.stdout


@pytest.mark.parametrize("action", ["infra", "run", "deploy", "stop"])
def test_missing_environment_fails_before_docker_mutation(workflow, action):
    run, root = workflow
    (root / ".env.local").unlink()
    result, calls = run(action)
    assert result.returncode != 0 and "make setup" in result.stderr
    assert not any(word in c for c in calls for word in ("up", "down", "run", "stop", "build"))


@pytest.mark.parametrize("failure", ["90 postgres redis", "alembic upgrade head"])
def test_deploy_failure_prevents_flask_start(workflow, failure):
    run, _ = workflow
    result, calls = run("deploy", FAIL=failure)
    assert result.returncode != 0
    assert not any(c.endswith("90 app") or "import-football" in c for c in commands(calls))


@pytest.mark.parametrize("signal", ["SIGINT", "SIGTERM"])
@pytest.mark.parametrize("stage", ["alembic upgrade head", "src/main.py"])
def test_interrupted_startup_exits_without_unrelated_cleanup(workflow, signal, stage):
    run, _ = workflow
    result, calls = run("run", INTERRUPT=stage, INTERRUPT_SIGNAL=signal)
    assert result.returncode != 0
    assert not any("--volumes" in c or "prune" in c or "kill" in c for c in commands(calls))
    assert not any("import-football" in c for c in commands(calls))
    if stage == "alembic upgrade head":
        assert ["python", "src/main.py"] not in calls


@pytest.mark.parametrize("action", ["run", "deploy"])
def test_compose_configuration_failure_stops_startup(workflow, action):
    run, _ = workflow
    result, calls = run(action, FAIL="config --quiet")
    assert result.returncode != 0
    assert not any(word in c for c in calls for word in ("up", "down", "run", "stop", "build"))


def test_inherited_project_name_cannot_redirect_owned_resources(workflow):
    run, _ = workflow
    result, calls = run("deploy", COMPOSE_PROJECT_NAME="unrelated-project")
    assert result.returncode == 0
    compose = [c for c in calls if c[:2] == ["docker", "compose"] and "--env-file" in c]
    assert compose
    assert all(c[c.index("-p") + 1] == "goalstats-service-local" for c in compose)
    assert not any("unrelated-project" in c for c in compose)


def seed_calls(calls):
    return [c for c in calls if "import-football" in c]


@pytest.mark.parametrize("dataset", APPROVED_DATASETS)
def test_seed_individual(workflow, dataset):
    run, _ = workflow
    result, calls = run("seed", DATASET=dataset)
    assert result.returncode == 0, result.stderr
    imports = seed_calls(calls)
    assert len(imports) == 1
    assert imports[0][imports[0].index("--dataset") + 1] == dataset
    assert "--dry-run" not in imports[0]


@pytest.mark.parametrize("dry", ["true", "false"])
def test_seed_group_order_allowlist_and_safety(workflow, dry):
    from football.historical_dataset import APPROVED_DATASETS

    run, _ = workflow
    result, calls = run("seed", DATASET="womens-world-cup", DRY=dry)
    assert result.returncode == 0, result.stderr
    imports = seed_calls(calls)
    assert [c[c.index("--dataset") + 1] for c in imports] == list(APPROVED_DATASETS)
    for c in imports:
        assert ("--dry-run" in c) == (dry == "true")
        assert c[c.index("--volume") + 1].endswith(":/input:ro")
        assert c[c.index("--expect-host") + 1] == "postgres"
        assert c[c.index("--expect-database") + 1] == "goal_stats_service_local"
        assert all(flag in c for flag in ("--rm", "--no-deps", "--pull", "never"))
    assert not any(
        word in c
        for c in calls
        for word in ("build", "pull", "up", "down", "upgrade", "--service-ports")
    )
    assert ("Confirmed committed inserts" in result.stdout) == (dry == "false")
    if dry == "true":
        assert "edition-local" in result.stdout and "own read-only snapshot" in result.stdout


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"DATASET": ""},
        {"DATASET": "prototype"},
        {"DATASET": "raw"},
        {"DATASET": "verification"},
        {"DATASET": "womens-world-cup-2027"},
        {"DATASET": "../data"},
        {"DATASET": "womens-world-cup-2023.json"},
        {"DATASET": "$(touch unsafe)"},
        *[{"DATASET": "womens-world-cup", "DRY": v} for v in ("", "TRUE", "0", "1", "yes")],
        {"DATASET": "womens-world-cup", "DRY_RUN": ""},
        {"DATASET": "womens-world-cup", "DRY": "true", "DRY_RUN": "1"},
    ],
)
def test_seed_invalid_options_before_docker(workflow, values):
    run, _ = workflow
    result, calls = run("seed", **values)
    assert result.returncode == 2
    assert calls == []


@pytest.mark.parametrize(
    "key",
    [
        "COMPOSE_FILE",
        "COMPOSE_PROJECT_NAME",
        "COMPOSE_PROFILES",
        "COMPOSE_ENV_FILES",
        "COMPOSE_PATH_SEPARATOR",
    ],
)
def test_seed_rejects_compose_overrides(workflow, key):
    run, _ = workflow
    result, calls = run("seed", DATASET="womens-world-cup", **{key: "private"})
    assert result.returncode == 2 and calls == []
    assert "private" not in result.stderr


@pytest.mark.parametrize(
    "extra",
    [
        {"FAIL": "image inspect"},
        {"NO_POSTGRES": "1"},
        {"STALE_IMAGE": "1"},
        {"FAIL": "python_environment.py config"},
        {"FAIL": "network inspect"},
    ],
)
def test_seed_preparation_failure_never_imports(workflow, extra):
    run, _ = workflow
    result, calls = run("seed", DATASET="womens-world-cup", **extra)
    assert result.returncode != 0 and not seed_calls(calls)


def test_seed_missing_source(workflow):
    run, root = workflow
    next(root.glob("data/raw/*/*/results.csv")).unlink()
    result, calls = run("seed", DATASET="womens-world-cup")
    assert result.returncode == 2 and calls == []


def test_seed_partial_failure_and_retry(workflow):
    run, _ = workflow
    result, calls = run("seed", DATASET="womens-world-cup", FAIL="--dataset womens-world-cup-1999")
    assert result.returncode == 7
    assert len(seed_calls(calls)) == 3
    assert "confirmed completed: womens-world-cup-1991 womens-world-cup-1995" in result.stderr
    assert "Not attempted: womens-world-cup-2003" in result.stderr
    assert "unconfirmed" in result.stderr
    assert not any("down" in c for c in calls)
    retry, _ = run("seed", DATASET="womens-world-cup")
    assert retry.returncode == 0


@pytest.mark.parametrize("signal,code", [("SIGINT", 130), ("SIGTERM", 143)])
def test_seed_interruption_scoped_cleanup(workflow, signal, code):
    run, _ = workflow
    result, calls = run(
        "seed", DATASET="womens-world-cup", INTERRUPT="import-football", INTERRUPT_SIGNAL=signal
    )
    assert result.returncode == code
    removals = [c for c in calls if c[:3] == ["docker", "rm", "-f"]]
    assert removals and all(c[-1].startswith("goalstats-seed-") for c in removals)
    assert not any("down" in c or "stop" in c for c in calls)


@pytest.mark.parametrize(
    "args",
    [
        ["DATASET=womens-world-cup-2023"],
        ["DATASET=womens-world-cup-2023", "DRY=true"],
    ],
)
def test_seed_real_make_dispatch(workflow, args):
    run, _ = workflow
    result, calls = run("seed", make_args=args)
    assert result.returncode == 0, result.stderr
    assert len(seed_calls(calls)) == 1
    assert ("--dry-run" in seed_calls(calls)[0]) == ("DRY=true" in args)


@pytest.mark.parametrize(
    "args",
    [
        ["DATASET=womens-world-cup", "DRY="],
        ["DATASET=womens-world-cup", "DRY_RUN="],
        ["DATASET=$(shell touch injected)"],
        ["DATASET=`touch injected`"],
        ["DATASET=womens-world-cup; touch injected"],
        ["DATASET=womens-world-cup", "DRY=$(shell touch injected)"],
    ],
)
def test_seed_real_make_rejects_unsafe_values(workflow, args):
    run, root = workflow
    result, calls = run("seed", make_args=args)
    assert result.returncode != 0 and calls == []
    assert not (root / "injected").exists()
