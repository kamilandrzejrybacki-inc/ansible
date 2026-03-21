"""Testinfra tests for nfs role."""


def test_nfs_server_installed(host):
    """Verify nfs-kernel-server is installed."""
    pkg = host.package("nfs-kernel-server")
    assert pkg.is_installed


def test_nfs_common_installed(host):
    """Verify nfs-common is installed."""
    pkg = host.package("nfs-common")
    assert pkg.is_installed


def test_nfs_exports_exists(host):
    """Verify /etc/exports is deployed."""
    f = host.file("/etc/exports")
    assert f.exists
    assert f.is_file
    assert f.mode == 0o644
    assert f.user == "root"


def test_nfs_exports_pool_share(host):
    """Verify mergerfs pool is exported."""
    f = host.file("/etc/exports")
    assert f.contains("/mnt/pool")
    assert f.contains("192.168.1.0/24")


def test_nfs_exports_internal_share(host):
    """Verify internal storage is exported."""
    f = host.file("/etc/exports")
    assert f.contains("/mnt/storage")


def test_nfs_exports_options(host):
    """Verify NFS export options are correct."""
    f = host.file("/etc/exports")
    assert f.contains("rw,sync,no_subtree_check")
    assert f.contains("root_squash")


def test_nfs_service_enabled(host):
    """Verify nfs-kernel-server service is enabled."""
    svc = host.service("nfs-kernel-server")
    assert svc.is_enabled
