"""Testinfra tests for fail2ban role."""


def test_fail2ban_installed(host):
    """Verify fail2ban is installed."""
    pkg = host.package("fail2ban")
    assert pkg.is_installed


def test_fail2ban_service_running(host):
    """Verify fail2ban service is running."""
    svc = host.service("fail2ban")
    assert svc.is_running
    assert svc.is_enabled


def test_jail_local_exists(host):
    """Verify jail.local configuration file exists."""
    cfg = host.file("/etc/fail2ban/jail.local")
    assert cfg.exists


def test_jail_local_sshd_enabled(host):
    """Verify sshd jail is configured."""
    cfg = host.file("/etc/fail2ban/jail.local")
    assert cfg.contains("sshd")


def test_jail_local_bantime(host):
    """Verify bantime is configured."""
    cfg = host.file("/etc/fail2ban/jail.local")
    assert cfg.contains("bantime")


def test_fail2ban_status(host):
    """Verify fail2ban is running and has the sshd jail."""
    result = host.run("fail2ban-client status")
    assert result.rc == 0
    assert "sshd" in result.stdout
