"""Testinfra tests for k9s role."""


def test_k9s_binary_exists(host):
    """Verify k9s binary exists at the expected path."""
    k9s = host.file("/usr/local/bin/k9s")
    assert k9s.exists
    assert k9s.mode & 0o111 != 0


def test_k9s_runs(host):
    """Verify k9s can report its version."""
    result = host.run("k9s version --short")
    assert result.rc == 0
