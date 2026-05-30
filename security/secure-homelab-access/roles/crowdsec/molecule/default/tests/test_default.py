"""Testinfra tests for crowdsec role."""


def test_crowdsec_data_dir(host):
    """Verify the CrowdSec data directory was created."""
    d = host.file("/opt/homelab/crowdsec")
    assert d.exists
    assert d.is_directory


def test_crowdsec_compose(host):
    """Verify the docker-compose config was written."""
    f = host.file("/opt/homelab/crowdsec/docker-compose.yml")
    assert f.exists
