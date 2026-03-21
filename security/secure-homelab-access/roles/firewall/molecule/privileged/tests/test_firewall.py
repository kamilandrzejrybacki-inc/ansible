"""Testinfra tests for firewall (UFW) role."""


def test_ufw_installed(host):
    """Verify UFW is installed."""
    ufw = host.package("ufw")
    assert ufw.is_installed


def test_ufw_active(host):
    """Verify UFW is active."""
    result = host.run("ufw status")
    assert "Status: active" in result.stdout


def test_ssh_allowed(host):
    """Verify SSH port 22 is allowed."""
    result = host.run("ufw status")
    assert "22/tcp" in result.stdout


def test_dns_tcp_allowed(host):
    """Verify DNS port 53 TCP is allowed."""
    result = host.run("ufw status")
    assert "53/tcp" in result.stdout


def test_wireguard_udp_allowed(host):
    """Verify WireGuard UDP port 51820 is allowed."""
    result = host.run("ufw status")
    assert "51820/udp" in result.stdout


def test_vpn_subnet_allowed(host):
    """Verify VPN subnet 10.8.0.0/24 is allowed."""
    result = host.run("ufw status")
    assert "10.8.0.0/24" in result.stdout


def test_default_deny_incoming(host):
    """Verify default policy denies incoming traffic."""
    result = host.run("ufw status verbose")
    assert "deny (incoming)" in result.stdout


def test_default_allow_outgoing(host):
    """Verify default policy allows outgoing traffic."""
    result = host.run("ufw status verbose")
    assert "allow (outgoing)" in result.stdout
