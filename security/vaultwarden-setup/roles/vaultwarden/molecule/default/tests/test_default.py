"""Testinfra tests for vaultwarden role."""


def test_vaultwarden_container_running(host):
    """Verify the Vaultwarden container is running."""
    result = host.run(
        "docker ps --filter name=vaultwarden --format '{{.Status}}'"
    )
    assert "Up" in result.stdout


def test_vaultwarden_port_listening(host):
    """Verify Vaultwarden is listening on port 8080 (localhost only)."""
    socket = host.socket("tcp://127.0.0.1:8080")
    assert socket.is_listening


def test_vaultwarden_data_dir_exists(host):
    """Verify the Vaultwarden data directory was created."""
    data_dir = host.file("/opt/vaultwarden")
    assert data_dir.is_directory


def test_vaultwarden_signups_disabled(host):
    """Verify signups are disabled via environment variable."""
    result = host.run(
        "docker inspect vaultwarden "
        "--format '{{range .Config.Env}}{{println .}}{{end}}'"
    )
    assert "SIGNUPS_ALLOWED=false" in result.stdout


def test_vaultwarden_health_check(host):
    """Verify Vaultwarden responds to HTTP requests."""
    result = host.run(
        "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080"
    )
    assert result.stdout in ("200", "302")
