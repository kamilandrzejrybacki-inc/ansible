"""Testinfra tests for paperless role."""


def test_paperless_container_running(host):
    """Verify the Paperless-ngx container is running."""
    result = host.run("docker ps --filter name=paperless --format '{{.Status}}'")
    assert "Up" in result.stdout


def test_paperless_port_listening(host):
    """Verify Paperless-ngx is listening on port 8000."""
    socket = host.socket("tcp://127.0.0.1:8000")
    assert socket.is_listening


def test_paperless_data_directory_exists(host):
    """Verify the Paperless data directory was created."""
    assert host.file("/opt/paperless").is_directory


def test_paperless_compose_file_exists(host):
    """Verify the Docker Compose file was templated."""
    compose = host.file("/opt/paperless/docker-compose.yml")
    assert compose.exists
    assert compose.mode == 0o600
