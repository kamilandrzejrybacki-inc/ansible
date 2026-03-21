"""Testinfra tests for seafile role."""


def test_seafile_container_running(host):
    """Verify the Seafile container is running."""
    result = host.run("docker ps --filter name=seafile --format '{{.Status}}'")
    assert "Up" in result.stdout


def test_seafile_port_listening(host):
    """Verify Seafile is listening on port 8080."""
    socket = host.socket("tcp://127.0.0.1:8080")
    assert socket.is_listening


def test_seafile_compose_directory_exists(host):
    """Verify the Seafile compose directory was created."""
    assert host.file("/opt/seafile").is_directory


def test_seafile_compose_file_exists(host):
    """Verify the Docker Compose file was templated."""
    compose = host.file("/opt/seafile/docker-compose.yml")
    assert compose.exists
    assert compose.mode == 0o600
