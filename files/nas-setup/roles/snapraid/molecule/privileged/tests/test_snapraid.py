"""Testinfra tests for snapraid role."""


def test_snapraid_config_exists(host):
    """Verify snapraid.conf is deployed."""
    f = host.file("/etc/snapraid.conf")
    assert f.exists
    assert f.is_file
    assert f.mode == 0o644
    assert f.user == "root"


def test_snapraid_config_parity(host):
    """Verify parity path is configured."""
    f = host.file("/etc/snapraid.conf")
    assert f.contains("parity /mnt/parity/parity1/snapraid.parity")


def test_snapraid_config_data_drives(host):
    """Verify data drives are configured."""
    f = host.file("/etc/snapraid.conf")
    assert f.contains("data disk1 /mnt/data/disk1")
    assert f.contains("data disk2 /mnt/data/disk2")
    assert f.contains("data disk3 /mnt/data/disk3")


def test_snapraid_config_content_files(host):
    """Verify content file paths are configured."""
    f = host.file("/etc/snapraid.conf")
    assert f.contains("content /mnt/data/disk1/.snapraid.content")
    assert f.contains("content /mnt/data/disk2/.snapraid.content")
    assert f.contains("content /mnt/data/disk3/.snapraid.content")


def test_snapraid_config_excludes(host):
    """Verify exclude patterns are present."""
    f = host.file("/etc/snapraid.conf")
    assert f.contains("exclude *.unrecoverable")
    assert f.contains("exclude /tmp/")
    assert f.contains("exclude /lost+found/")


def test_snapraid_sync_script(host):
    """Verify sync script is deployed."""
    f = host.file("/usr/local/bin/snapraid-sync")
    assert f.exists
    assert f.is_file
    assert f.mode == 0o755
    assert f.user == "root"


def test_snapraid_sync_script_content(host):
    """Verify sync script contains threshold check."""
    f = host.file("/usr/local/bin/snapraid-sync")
    assert f.contains("snapraid diff")
    assert f.contains("snapraid sync")
    assert f.contains("40")


def test_snapraid_scrub_script(host):
    """Verify scrub script is deployed."""
    f = host.file("/usr/local/bin/snapraid-scrub")
    assert f.exists
    assert f.is_file
    assert f.mode == 0o755
    assert f.user == "root"


def test_snapraid_scrub_script_content(host):
    """Verify scrub script contains scrub command."""
    f = host.file("/usr/local/bin/snapraid-scrub")
    assert f.contains("snapraid scrub")


def test_snapraid_log_file(host):
    """Verify snapraid log file exists."""
    f = host.file("/var/log/snapraid.log")
    assert f.exists
    assert f.is_file


def test_snapraid_sync_cron(host):
    """Verify sync cron job is scheduled."""
    cron = host.run("crontab -l -u root")
    assert "/usr/local/bin/snapraid-sync" in cron.stdout
    assert "0 3" in cron.stdout


def test_snapraid_scrub_cron(host):
    """Verify scrub cron job is scheduled."""
    cron = host.run("crontab -l -u root")
    assert "/usr/local/bin/snapraid-scrub" in cron.stdout
