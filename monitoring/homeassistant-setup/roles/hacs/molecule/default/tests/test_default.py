"""Testinfra tests for homeassistant hacs role."""


def test_custom_components_dir(host):
    """Verify custom_components directory exists."""
    d = host.file("/tmp/test-ha-config/custom_components")
    assert d.exists
    assert d.is_directory


def test_hacs_dir(host):
    """Verify HACS integration directory exists."""
    d = host.file("/tmp/test-ha-config/custom_components/hacs")
    assert d.exists
    assert d.is_directory


def test_hacs_manifest(host):
    """Verify HACS manifest.json is present."""
    manifest = host.file(
        "/tmp/test-ha-config/custom_components/hacs/manifest.json"
    )
    assert manifest.exists
    assert manifest.is_file


def test_hacs_init(host):
    """Verify HACS __init__.py is present."""
    init = host.file(
        "/tmp/test-ha-config/custom_components/hacs/__init__.py"
    )
    assert init.exists
    assert init.is_file


def test_temp_zip_cleaned(host):
    """Verify temporary zip file was removed."""
    assert not host.file("/tmp/hacs.zip").exists
