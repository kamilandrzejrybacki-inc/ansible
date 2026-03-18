"""Testinfra tests for prerequisites role."""


def test_docker_installed(host):
    """Verify Docker is installed."""
    result = host.run("docker --version")
    assert result.rc == 0


def test_docker_compose_plugin(host):
    """Verify Docker Compose plugin is available."""
    result = host.run("docker compose version")
    assert result.rc == 0


def test_git_installed(host):
    """Verify Git is installed."""
    result = host.run("git --version")
    assert result.rc == 0
