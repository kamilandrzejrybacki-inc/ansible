"""Testinfra tests for docker role (netbox)."""
import pytest


@pytest.mark.parametrize("pkg", [
    "docker-ce",
    "docker-ce-cli",
    "containerd.io",
    "docker-compose-plugin",
])
def test_docker_packages(host, pkg):
    """Verify Docker packages are installed."""
    assert host.package(pkg).is_installed
