"""Testinfra tests for i3lock_color role."""


def test_i3lock_binary_exists(host):
    """Verify i3lock binary exists at the expected path."""
    i3lock = host.file("/usr/local/bin/i3lock")
    assert i3lock.exists
    assert i3lock.mode & 0o111 != 0


def test_i3lock_runs(host):
    """Verify i3lock binary can report its version."""
    result = host.run("/usr/local/bin/i3lock --version")
    assert result.rc == 0 or "i3lock" in result.stderr
