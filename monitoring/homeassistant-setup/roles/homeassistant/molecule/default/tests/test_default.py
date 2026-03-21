"""Testinfra tests for homeassistant role."""


def test_homeassistant_container_running(host):
    """Verify the Home Assistant container is running."""
    result = host.run(
        "docker ps --filter name=homeassistant --format '{{.Status}}'"
    )
    assert "Up" in result.stdout


def test_homeassistant_port_listening(host):
    """Verify Home Assistant is listening on port 8123."""
    socket = host.socket("tcp://0.0.0.0:8123")
    assert socket.is_listening


def test_homeassistant_config_directory_exists(host):
    """Verify the Home Assistant config directory was created."""
    assert host.file("/opt/homeassistant/config").is_directory


def test_homeassistant_health_check(host):
    """Verify Home Assistant responds to HTTP requests."""
    result = host.run(
        "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8123"
    )
    assert result.stdout in ("200", "302")
