"""Testinfra tests for fastfetch role."""


def test_fastfetch_binary_exists(host):
    """Verify fastfetch binary is available on PATH."""
    result = host.run("which fastfetch")
    assert result.rc == 0


def test_fastfetch_runs(host):
    """Verify fastfetch can execute."""
    result = host.run("fastfetch --version")
    assert result.rc == 0
