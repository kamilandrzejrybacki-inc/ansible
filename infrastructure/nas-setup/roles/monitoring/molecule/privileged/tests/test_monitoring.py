"""Testinfra tests for monitoring role."""


def test_smartmontools_installed(host):
    """Verify smartmontools is installed."""
    pkg = host.package("smartmontools")
    assert pkg.is_installed


def test_smartd_config_exists(host):
    """Verify smartd.conf is deployed."""
    f = host.file("/etc/smartd.conf")
    assert f.exists
    assert f.is_file
    assert f.mode == 0o644
    assert f.user == "root"


def test_smartd_config_data_drives(host):
    """Verify data drives are configured in smartd.conf."""
    f = host.file("/etc/smartd.conf")
    assert f.contains("/dev/sdb")
    assert f.contains("/dev/sdc")
    assert f.contains("/dev/sdd")


def test_smartd_config_parity_drive(host):
    """Verify parity drive is configured in smartd.conf."""
    f = host.file("/etc/smartd.conf")
    assert f.contains("/dev/sde")


def test_smartd_config_internal_drive(host):
    """Verify internal drive is configured in smartd.conf."""
    f = host.file("/etc/smartd.conf")
    assert f.contains("/dev/sda")


def test_smartd_config_email(host):
    """Verify alert email is configured."""
    f = host.file("/etc/smartd.conf")
    assert f.contains("test@example.com")


def test_smartd_config_monitoring_options(host):
    """Verify SMART monitoring options are present."""
    f = host.file("/etc/smartd.conf")
    assert f.contains("-a -o on -S on")
    assert f.contains("-W 4,45,50")


def test_smartd_service_enabled(host):
    """Verify smartd service is enabled."""
    svc = host.service("smartd")
    assert svc.is_enabled
