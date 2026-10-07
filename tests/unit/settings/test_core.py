import pytest

from settings.base import ConfigurationError, Environment
from settings.core import CoreSettings


@pytest.mark.parametrize("mode", list(Environment))
def test_typed_core_is_immutable_and_validated(mode):
    from dataclasses import FrozenInstanceError

    core = CoreSettings(app_env=mode)
    assert core.host_app_port == 5100
    with pytest.raises(FrozenInstanceError):
        core.host_app_port = 1


@pytest.mark.parametrize("port", [0, 65536, True])
def test_typed_core_rejects_bad_port(port):
    with pytest.raises(ConfigurationError):
        CoreSettings(host_app_port=port)
