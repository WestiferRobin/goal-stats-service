"""Readiness policy and short-circuiting without HTTP or real providers."""

from unittest.mock import Mock

import pytest

from infra import base


@pytest.mark.parametrize(
    "database_ready,cache_ready,expected",
    [
        (True, True, "Healthy"),
        (True, False, "Degraded"),
        (False, True, "Unhealthy"),
        (False, False, "Unhealthy"),
    ],
)
def test_dependency_policy_and_cache_short_circuit(
    monkeypatch, database_ready, cache_ready, expected
):
    database = object()
    probe = Mock(return_value=database_ready)
    cache = Mock()
    cache.ready.return_value = cache_ready
    monkeypatch.setattr(base, "is_ready", probe)
    assert base.readiness(database, cache, "owned-prefix") == expected
    probe.assert_called_once_with(database)
    if database_ready:
        cache.ready.assert_called_once_with("owned-prefix")
    else:
        cache.ready.assert_not_called()


@pytest.mark.parametrize("dependency", ["database", "cache"])
def test_unexpected_probe_errors_propagate(monkeypatch, dependency):
    probe = Mock(return_value=True)
    cache = Mock()
    failure = RuntimeError("probe failure")
    (probe if dependency == "database" else cache.ready).side_effect = failure
    monkeypatch.setattr(base, "is_ready", probe)
    with pytest.raises(RuntimeError) as caught:
        base.readiness(object(), cache, "prefix")
    assert caught.value is failure
    if dependency == "database":
        cache.ready.assert_not_called()
