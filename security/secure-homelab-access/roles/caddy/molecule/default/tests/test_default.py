"""Testinfra tests for caddy role."""


def test_caddy_container_running(host):
    """Verify the Caddy container is running."""
    result = host.run("docker ps --filter name=caddy --format '{{.Status}}'")
    assert "Up" in result.stdout


def test_caddy_port_80_listening(host):
    """Verify Caddy is listening on port 80."""
    socket = host.socket("tcp://0.0.0.0:80")
    assert socket.is_listening


def test_caddy_port_443_listening(host):
    """Verify Caddy is listening on port 443."""
    socket = host.socket("tcp://0.0.0.0:443")
    assert socket.is_listening


def test_caddy_data_directory_exists(host):
    """Verify the Caddy data directories were created."""
    assert host.file("/opt/homelab/caddy").is_directory
    assert host.file("/opt/homelab/caddy/config").is_directory
    assert host.file("/opt/homelab/caddy/data").is_directory
