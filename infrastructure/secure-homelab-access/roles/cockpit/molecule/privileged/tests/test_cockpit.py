"""Testinfra tests for cockpit role."""


def test_cockpit_installed(host):
    """Verify cockpit package is installed."""
    pkg = host.package("cockpit")
    assert pkg.is_installed


def test_cockpit_storaged_installed(host):
    """Verify cockpit-storaged package is installed."""
    pkg = host.package("cockpit-storaged")
    assert pkg.is_installed


def test_cockpit_networkmanager_installed(host):
    """Verify cockpit-networkmanager package is installed."""
    pkg = host.package("cockpit-networkmanager")
    assert pkg.is_installed


def test_cockpit_packagekit_installed(host):
    """Verify cockpit-packagekit package is installed."""
    pkg = host.package("cockpit-packagekit")
    assert pkg.is_installed


def test_cockpit_config_exists(host):
    """Verify cockpit.conf is deployed."""
    f = host.file("/etc/cockpit/cockpit.conf")
    assert f.exists
    assert f.is_file
    assert f.mode == 0o644


def test_cockpit_config_content(host):
    """Verify cockpit.conf contains expected configuration."""
    f = host.file("/etc/cockpit/cockpit.conf")
    assert f.contains("AllowUnencrypted=true")
    assert f.contains("Origins=https://cockpit.example.test")


def test_cockpit_socket_enabled(host):
    """Verify cockpit.socket is enabled."""
    svc = host.service("cockpit.socket")
    assert svc.is_enabled
