"""Load the stdlib-only settings package from its explicit repository location."""

import importlib
import importlib.util
import sys
from pathlib import Path

_directory = Path(__file__).resolve().parents[2] / "src/settings"
if "settings" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "settings", _directory / "__init__.py", submodule_search_locations=[str(_directory)]
    )
    assert _spec is not None and _spec.loader is not None
    _package = importlib.util.module_from_spec(_spec)
    sys.modules["settings"] = _package
    _spec.loader.exec_module(_package)
schema = importlib.import_module("settings.environment")
