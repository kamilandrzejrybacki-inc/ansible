"""Testinfra tests for litellm role."""


def test_litellm_directory(host):
    """Verify the LiteLLM install directory was created."""
    d = host.file("/opt/litellm")
    assert d.exists
    assert d.is_directory


def test_litellm_config(host):
    """Verify the LiteLLM config was written."""
    f = host.file("/opt/litellm/litellm-config.yaml")
    assert f.exists


def test_litellm_compose(host):
    """Verify the docker-compose.yml was written."""
    f = host.file("/opt/litellm/docker-compose.yml")
    assert f.exists
