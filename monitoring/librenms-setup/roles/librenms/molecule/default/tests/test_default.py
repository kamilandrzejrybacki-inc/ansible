"""Testinfra tests for librenms role."""


def test_librenms_data_dir(host):
    """Verify the LibreNMS data directory was created."""
    d = host.file("/opt/librenms")
    assert d.exists
    assert d.is_directory


def test_librenms_compose(host):
    """Verify the docker-compose.yml was written."""
    f = host.file("/opt/librenms/docker-compose.yml")
    assert f.exists
    assert f.mode == 0o640
