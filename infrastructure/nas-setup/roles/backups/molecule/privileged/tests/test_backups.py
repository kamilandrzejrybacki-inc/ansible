"""Testinfra tests for backups role."""


def test_rsync_installed(host):
    """Verify rsync is installed."""
    pkg = host.package("rsync")
    assert pkg.is_installed


def test_backup_dest_directory(host):
    """Verify backup destination directory exists."""
    d = host.file("/mnt/storage/backups")
    assert d.exists
    assert d.is_directory


def test_backup_script_deployed(host):
    """Verify backup script is deployed."""
    f = host.file("/usr/local/bin/nas-backup")
    assert f.exists
    assert f.is_file
    assert f.mode == 0o755
    assert f.user == "root"
    assert f.group == "root"


def test_backup_script_content(host):
    """Verify backup script contains expected rsync command."""
    f = host.file("/usr/local/bin/nas-backup")
    assert f.contains("rsync")
    assert f.contains("/mnt/pool")
    assert f.contains("/mnt/storage/backups")


def test_backup_log_file(host):
    """Verify backup log file exists."""
    f = host.file("/var/log/nas-backup.log")
    assert f.exists
    assert f.is_file
    assert f.mode == 0o644


def test_backup_cron_entry(host):
    """Verify backup cron job is scheduled."""
    cron = host.run("crontab -l -u root")
    assert "/usr/local/bin/nas-backup" in cron.stdout
    assert "0 4" in cron.stdout
