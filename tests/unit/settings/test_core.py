import pytest

from settings.base import ConfigurationError, Environment
from settings.core import CoreSettings


@pytest.mark.parametrize("mode", list(Environment))
def test_typed_core_is_immutable_and_validated(mode):
    from dataclasses import FrozenInstanceError

    core = CoreSettings(app_env=mode, service_api_token="test-token-" * 4)
    assert core.host_app_port == 5100
    with pytest.raises(FrozenInstanceError):
        core.host_app_port = 1


@pytest.mark.parametrize("port", [0, 65536, True])
def test_typed_core_rejects_bad_port(port):
    with pytest.raises(ConfigurationError):
        CoreSettings(host_app_port=port)


@pytest.mark.parametrize("value", ["true", 1, None])
def test_typed_core_rejects_nonboolean_openapi_values(value):
    """Typed configuration must not silently coerce strings or integers into feature flags."""
    with pytest.raises(ConfigurationError, match="OPENAPI_ENABLED must be a boolean"):
        CoreSettings(openapi_enabled=value)
