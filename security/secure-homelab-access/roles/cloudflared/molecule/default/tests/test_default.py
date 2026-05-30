"""Testinfra tests for cloudflared role."""


def test_cloudflared_binary(host):
    """Verify cloudflared binary is installed."""
    f = host.file("/usr/local/bin/cloudflared")
    assert f.exists


def test_cloudflared_config_dir(host):
    """Verify cloudflared config directory was created."""
    d = host.file("/etc/cloudflared")
    assert d.exists
    assert d.is_directory
