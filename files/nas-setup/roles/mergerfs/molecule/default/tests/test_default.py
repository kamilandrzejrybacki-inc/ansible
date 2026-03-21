"""Smoke tests for mergerfs role (Docker - install only)."""


def test_mergerfs_binary_installed(host):
    """Verify mergerfs binary is available."""
    result = host.run("mergerfs --version")
    assert result.rc == 0


def test_fuse3_installed(host):
    """Verify fuse3 package is installed."""
    fuse = host.package("fuse3")
    assert fuse.is_installed
