"""Testinfra tests for openclaw role."""


def test_openclaw_directory(host):
    """Verify the OpenClaw install directory was created."""
    d = host.file("/opt/openclaw")
    assert d.exists
    assert d.is_directory
    assert d.mode == 0o700


def test_openclaw_config(host):
    """Verify the OpenClaw config was written."""
    f = host.file("/opt/openclaw/config.json")
    assert f.exists
    assert f.mode == 0o600


def test_openclaw_compose(host):
    """Verify the docker-compose.yml was written."""
    f = host.file("/opt/openclaw/docker-compose.yml")
    assert f.exists
    assert f.mode == 0o644


def test_openclaw_data_dir(host):
    """Verify the data directory was created."""
    d = host.file("/opt/openclaw/data")
    assert d.exists
    assert d.is_directory
