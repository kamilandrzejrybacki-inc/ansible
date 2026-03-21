"""Testinfra tests for wireguard role."""


def test_ip_forwarding_enabled(host):
    """Verify IPv4 forwarding is enabled via sysctl."""
    result = host.run("sysctl -n net.ipv4.ip_forward")
    assert result.stdout.strip() == "1"


def test_src_valid_mark_enabled(host):
    """Verify src_valid_mark sysctl is enabled."""
    result = host.run("sysctl -n net.ipv4.conf.all.src_valid_mark")
    assert result.stdout.strip() == "1"


def test_wireguard_data_directory(host):
    """Verify WireGuard data directory exists with correct permissions."""
    d = host.file("/opt/homelab/wireguard")
    assert d.exists
    assert d.is_directory
    assert d.mode == 0o700


def test_wireguard_container_running(host):
    """Verify the wg-easy container is running."""
    result = host.run("docker ps --filter name=wg-easy --format '{{.Status}}'")
    assert "Up" in result.stdout


def test_wireguard_udp_port(host):
    """Verify WireGuard UDP port 51820 is exposed."""
    result = host.run("docker ps --filter name=wg-easy --format '{{.Ports}}'")
    assert "51820" in result.stdout


def test_wireguard_web_port(host):
    """Verify WireGuard web UI port 51821 is bound to localhost."""
    result = host.run("docker ps --filter name=wg-easy --format '{{.Ports}}'")
    assert "127.0.0.1" in result.stdout
    assert "51821" in result.stdout


def test_docker_network_exists(host):
    """Verify the homelab-net Docker network exists."""
    result = host.run("docker network inspect homelab-net")
    assert result.rc == 0
