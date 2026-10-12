"""Small stdlib-only host bootstrap and read-only dependency verification."""

import json
import os
import subprocess
import sys
from pathlib import Path


def probe(executable, root):
    """Inspect the selected interpreter, never import application configuration."""
    if not (root / "requirements.txt").is_file():
        raise RuntimeError("requirements.txt is missing; restore the tracked dependency file.")
    code = """
import importlib.metadata as m, json, re, sys
from pathlib import Path
missing = []
for line in Path(sys.argv[1]).read_text().splitlines():
    line = line.strip()
    if not line or line.startswith('#'): continue
    match = re.fullmatch(r'([A-Za-z0-9_.-]+)(?:\\[[A-Za-z0-9_,.-]+\\])?==([^ ;]+)', line)
    if not match: raise SystemExit('requirements.txt must contain exact package pins')
    name, expected = match.groups()
    try: actual = m.version(name)
    except m.PackageNotFoundError: actual = None
    if actual != expected: missing.append(name)
print(json.dumps({'version': list(sys.version_info[:2]), 'prefix': sys.prefix,
                 'base': sys.base_prefix, 'missing': missing}))
"""
    try:
        result = subprocess.run(
            [str(executable), "-I", "-B", "-c", code, str(root / "requirements.txt")],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode:
            raise ValueError
        return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        raise RuntimeError(
            "Cannot inspect .venv Python; repair the interpreter, then make setup."
        ) from None


def verify(root, *, dependencies=True):
    venv = root / ".venv"
    executable = venv / "bin/python"
    if venv.is_symlink():
        raise RuntimeError(".venv must be a repository-local directory, not a symlink.")
    if not executable.is_file():
        raise RuntimeError(".venv/bin/python is missing. Run make setup.")
    info = probe(executable, root)
    if (
        info["version"] != [3, 12]
        or Path(info["prefix"]).resolve() != venv.resolve()
        or info["prefix"] == info["base"]
    ):
        raise RuntimeError(
            ".venv must use Python 3.12. Move the incompatible venv aside, then make setup."
        )
    if dependencies:
        if info["missing"]:
            raise RuntimeError(
                "requirements.txt dependency mismatch: "
                + ", ".join(info["missing"])
                + ". Run make setup."
            )
        try:
            result = subprocess.run(
                [str(executable), "-I", "-B", "-m", "pip", "check"],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError("Cannot check .venv dependencies. Run make setup.") from None
        if result.returncode:
            raise RuntimeError(
                ".venv dependency consistency failed. Run make setup; "
                "if it persists, recreate only .venv."
            )
    return info


def bootstrap(root):
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError(
            "Python 3.12 is required. Install it and run make setup PYTHON=python3.12."
        )
    venv = root / ".venv"
    if not venv.exists() and not venv.is_symlink():
        print("Creating repository .venv with Python 3.12", flush=True)
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    info = verify(root, dependencies=False)
    executable = venv / "bin/python"
    if info["missing"]:
        print("Installing pinned requirements.txt into .venv", flush=True)
        subprocess.run(
            [
                str(executable),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-r",
                str(root / "requirements.txt"),
            ],
            check=True,
            env={**os.environ, "PIP_REQUIRE_VIRTUALENV": "true"},
        )
    verify(root)
    print("Python 3.12 .venv and pinned dependencies ready (existing valid installs reused).")


def main():
    import argparse

    from environment_config import schema

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("bootstrap", "verify", "config", "port"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Python 3.12 is required. Select it with make setup PYTHON=python3.12.")
    if args.action == "bootstrap":
        bootstrap(root)
    elif args.action == "verify":
        verify(root)
    elif args.action == "config":
        print(schema.local_runtime()["HOST_APP_PORT"])
    else:
        schema.check_local_port()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as exc:
        sys.exit(str(exc))
