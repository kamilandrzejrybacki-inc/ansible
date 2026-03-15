"""Testinfra tests for seafile caddy role."""


def test_caddy_container_running(host):
    """Verify the Caddy container is running."""
    result = host.run(
        "docker ps --filter name=seafile-caddy --format '{{.Status}}'"
    )
    assert "Up" in result.stdout


def test_caddy_config_directory_exists(host):
    """Verify the Caddy config directory was created."""
    assert host.file("/opt/seafile/caddy").is_directory


def test_caddyfile_exists(host):
    """Verify the Caddyfile was templated."""
    caddyfile = host.file("/opt/seafile/caddy/Caddyfile")
    assert caddyfile.exists
    assert caddyfile.mode == 0o644
