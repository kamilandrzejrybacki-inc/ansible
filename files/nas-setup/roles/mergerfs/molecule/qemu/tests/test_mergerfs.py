"""Testinfra tests for mergerfs role (QEMU - full mount test)."""


def test_mergerfs_binary_installed(host):
    """Verify mergerfs binary is available."""
    result = host.run("mergerfs --version")
    assert result.rc == 0


def test_fuse3_installed(host):
    """Verify fuse3 package is installed."""
    fuse = host.package("fuse3")
    assert fuse.is_installed


def test_mergerfs_mount_exists(host):
    """Verify mergerfs pool is mounted."""
    mount = host.mount_point("/mnt/pool")
    assert mount.exists
    assert mount.filesystem == "fuse.mergerfs"


def test_mergerfs_fstab_entry(host):
    """Verify mergerfs is configured in fstab."""
    fstab = host.file("/etc/fstab")
    assert fstab.exists
    assert "/mnt/pool" in fstab.content_string
    assert "mergerfs" in fstab.content_string


def test_data_drives_mounted(host):
    """Verify individual data drives are mounted."""
    for i in range(1, 4):
        mount = host.mount_point(f"/mnt/data/disk{i}")
        assert mount.exists
        assert mount.filesystem == "ext4"


def test_mergerfs_pool_writable(host):
    """Verify the mergerfs pool is writable."""
    result = host.run("touch /mnt/pool/test-file && rm /mnt/pool/test-file")
    assert result.rc == 0
