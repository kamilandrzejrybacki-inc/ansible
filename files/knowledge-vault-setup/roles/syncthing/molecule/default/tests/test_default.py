"""Testinfra tests for syncthing role."""


def test_syncthing_data_directory_exists(host):
    """Verify the Syncthing data directory was created."""
    assert host.file("/opt/knowledge-vault/syncthing").is_directory


def test_syncthing_content_directory_exists(host):
    """Verify the shared vault content directory was created."""
    assert host.file("/opt/knowledge-vault/content").is_directory


def test_syncthing_compose_file_exists(host):
    """Verify the Docker Compose file was templated."""
    compose = host.file("/opt/knowledge-vault/syncthing/docker-compose.yml")
    assert compose.exists
    assert compose.mode == 0o600


def test_syncthing_container_running(host):
    """Verify the Syncthing container is running."""
    result = host.run("docker ps --filter name=syncthing --format '{{.Status}}'")
    assert "Up" in result.stdout


def test_syncthing_sync_port_listening(host):
    """Verify Syncthing sync protocol is listening."""
    socket = host.socket("tcp://0.0.0.0:22000")
    assert socket.is_listening


def test_syncthing_ui_port_listening(host):
    """Verify Syncthing Web UI is listening on localhost."""
    socket = host.socket("tcp://127.0.0.1:8384")
    assert socket.is_listening


def test_syncthing_api_responds(host):
    """Verify Syncthing API is accessible."""
    result = host.run("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8384/rest/system/status")
    assert result.stdout.strip() in ["200", "401", "403"]
