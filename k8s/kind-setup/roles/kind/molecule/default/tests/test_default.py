"""Testinfra tests for kind role."""


def test_kind_binary_exists(host):
    """Verify kind binary exists at the expected path."""
    kind = host.file("/usr/local/bin/kind")
    assert kind.exists
    assert kind.mode & 0o111 != 0


def test_kind_runs(host):
    """Verify kind can report its version."""
    result = host.run("kind version")
    assert result.rc == 0


def test_kubectl_installed(host):
    """Verify kubectl is installed."""
    result = host.run("kubectl version --client")
    assert result.rc == 0
