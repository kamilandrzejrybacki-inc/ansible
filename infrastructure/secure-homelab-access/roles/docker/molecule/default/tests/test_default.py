"""Testinfra tests for docker role."""


def test_docker_installed(host):
    """Verify Docker CE is installed."""
    docker = host.package("docker-ce")
    assert docker.is_installed


def test_docker_cli_installed(host):
    """Verify Docker CLI is installed."""
    cli = host.package("docker-ce-cli")
    assert cli.is_installed


def test_containerd_installed(host):
    """Verify containerd is installed."""
    containerd = host.package("containerd.io")
    assert containerd.is_installed


def test_docker_compose_plugin_installed(host):
    """Verify docker-compose-plugin package is installed."""
    result = host.package("docker-compose-plugin")
    assert result.is_installed


def test_docker_data_directory_exists(host):
    """Verify the homelab data directory is created."""
    data_dir = host.file("/opt/homelab")
    assert data_dir.exists
    assert data_dir.is_directory
    assert data_dir.mode == 0o755


def test_docker_network_exists(host):
    """Verify the homelab Docker network is created."""
    result = host.run("docker network inspect homelab-net")
    assert result.rc == 0
