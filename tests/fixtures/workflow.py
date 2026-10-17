"""Recording executables for canonical local workflow tests."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def workflow(tmp_path):
    (tmp_path / "scripts/development").mkdir(parents=True)
    shutil.copy(ROOT / "scripts/development/local.sh", tmp_path / "scripts/development/local.sh")
    shutil.copy(ROOT / "Makefile", tmp_path / "Makefile")
    shutil.copy(ROOT / ".env.example", tmp_path / ".env.example")
    shutil.copy(ROOT / ".env.example", tmp_path / ".env.local")
    (tmp_path / ".venv/bin").mkdir(parents=True)
    source = tmp_path / "data/raw/martj42-womens-results/1855e313ae8bcd0330426e62c8e4cf15ce45077c"
    source.mkdir(parents=True)
    (source / "results.csv").write_text("fixture")
    binary = tmp_path / "bin"
    binary.mkdir()
    # These stubs only record invocations; the lifecycle under test is unmodified.
    stub = (
        "#!"
        + sys.executable
        + """
import json, os, signal, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['RECORD'], 'a') as f:
    f.write(json.dumps([name, *args]) + '\\n')
if os.environ.get('INTERRUPT') and os.environ['INTERRUPT'] in ' '.join(args):
    if 'import-football' in args:
        os.kill(os.getppid(), getattr(signal, os.environ['INTERRUPT_SIGNAL']))
        __import__('time').sleep(10)
    else:
        os.kill(os.getpid(), getattr(signal, os.environ['INTERRUPT_SIGNAL']))
if os.environ.get('FAIL') and os.environ['FAIL'] in ' '.join(args):
    sys.exit(7)
if name == 'make':
    print('GNU Make 4.0')
    if os.environ.get('LARGE_MAKE_VERSION'): print('version details' * 20000)
if args == ['scripts/development/python_environment.py', 'config']: print('5100')
if 'ps' in args:
    if args[-1] == 'postgres' and not os.environ.get('NO_POSTGRES'): print('owned-postgres')
    elif os.environ.get('APP_RUNNING'): print('owned-app')
if args[:2] == ['inspect', '--format']: print('healthy')
if name == 'docker' and 'import-football' in args:
    print(json.dumps(dict(committed='--dry-run' not in args,
        insert_counts='proposed' if '--dry-run' in args else 'committed',
        teams_inserted=1,competitions_inserted=1,matches_inserted=26)))
if '-c' in args:
    code=args[args.index('-c')+1]
    if 'import secrets' in code: print('a'*24)
    elif 'hashlib.sha256(json.dumps' in code:
        print('stale' if name == 'docker' and os.environ.get('STALE_IMAGE') else 'fingerprint')
    elif 'json.load(open' in code: print('1 1 26')
if 'port' in args and name == 'docker': print('127.0.0.1:5100')
"""
    )
    for path in [
        binary / "docker",
        binary / "make",
        binary / "python3.12",
        tmp_path / ".venv/bin/python",
    ]:
        path.write_text(stub)
        path.chmod(0o755)

    def execute(action, make_args=None, **extra):
        record = tmp_path / "record"
        record.write_text("")
        env = {
            **os.environ,
            "PATH": str(binary) + os.pathsep + os.environ["PATH"],
            "PYTHON": "python3.12",
            "RECORD": str(record),
            **extra,
        }
        arguments = ["bash", "scripts/development/local.sh", action]
        if make_args is not None:
            make = shutil.which("make")
            if make is None:
                pytest.skip("GNU Make unavailable in tooling; real dispatch is tested on the host")
            arguments = [make, action, *make_args]
        result = subprocess.run(
            arguments,
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
        )
        calls = [json.loads(line) for line in record.read_text().splitlines()]
        return result, calls

    return execute, tmp_path
