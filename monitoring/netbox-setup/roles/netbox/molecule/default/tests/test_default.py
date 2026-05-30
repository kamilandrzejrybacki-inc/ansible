"""Testinfra tests for netbox role."""


def test_netbox_data_dir(host):
    """Verify the Netbox data directory was created."""
    d = host.file("/opt/netbox")
    assert d.exists
    assert d.is_directory


def test_netbox_compose(host):
    """Verify the docker-compose.yml was written."""
    f = host.file("/opt/netbox/docker-compose.yml")
    assert f.exists


def test_netbox_media_dir(host):
    """Verify subdirectories were created."""
    for d in ["/opt/netbox/media", "/opt/netbox/reports", "/opt/netbox/scripts"]:
        directory = host.file(d)
        assert directory.exists
        assert directory.is_directory
