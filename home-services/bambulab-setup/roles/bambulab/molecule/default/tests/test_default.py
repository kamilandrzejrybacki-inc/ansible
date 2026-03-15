"""Testinfra tests for bambulab role."""


def test_custom_components_dir(host):
    """Verify custom_components directory exists."""
    d = host.file("/tmp/test-ha-config/custom_components")
    assert d.exists
    assert d.is_directory


def test_bambu_lab_dir(host):
    """Verify bambu_lab integration directory exists."""
    d = host.file("/tmp/test-ha-config/custom_components/bambu_lab")
    assert d.exists
    assert d.is_directory


def test_bambu_lab_manifest(host):
    """Verify bambu_lab manifest.json is present."""
    manifest = host.file(
        "/tmp/test-ha-config/custom_components/bambu_lab/manifest.json"
    )
    assert manifest.exists
    assert manifest.is_file


def test_bambu_lab_init(host):
    """Verify bambu_lab __init__.py is present."""
    init = host.file(
        "/tmp/test-ha-config/custom_components/bambu_lab/__init__.py"
    )
    assert init.exists
    assert init.is_file


def test_temp_zip_cleaned(host):
    """Verify temporary zip file was removed."""
    assert not host.file("/tmp/bambulab.zip").exists
