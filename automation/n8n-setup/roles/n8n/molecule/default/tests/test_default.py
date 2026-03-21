"""Testinfra tests for n8n role."""


def test_n8n_container_running(host):
    """Verify the n8n container is running."""
    result = host.run("docker ps --filter name=n8n --format '{{.Status}}'")
    assert "Up" in result.stdout


def test_n8n_port_listening(host):
    """Verify n8n is listening on port 5678 (localhost only)."""
    socket = host.socket("tcp://127.0.0.1:5678")
    assert socket.is_listening


def test_n8n_volume_exists(host):
    """Verify the n8n data volume was created."""
    result = host.run("docker volume inspect n8n_data")
    assert result.rc == 0


def test_n8n_health_check(host):
    """Verify n8n responds to HTTP requests."""
    result = host.run(
        "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5678"
    )
    assert result.stdout in ("200", "302")
