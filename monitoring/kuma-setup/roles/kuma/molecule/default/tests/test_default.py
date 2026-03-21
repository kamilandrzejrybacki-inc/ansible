"""Testinfra tests for kuma role."""


def test_kuma_container_running(host):
    """Verify the Uptime Kuma container is running."""
    result = host.run("docker ps --filter name=kuma --format '{{.Status}}'")
    assert "Up" in result.stdout


def test_kuma_port_listening(host):
    """Verify Kuma is listening on port 3001 (localhost only)."""
    socket = host.socket("tcp://127.0.0.1:3001")
    assert socket.is_listening


def test_kuma_volume_exists(host):
    """Verify the Kuma data volume was created."""
    result = host.run("docker volume inspect kuma_data")
    assert result.rc == 0


def test_kuma_health_check(host):
    """Verify Kuma responds to HTTP requests."""
    result = host.run(
        "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3001"
    )
    assert result.stdout in ("200", "302")
