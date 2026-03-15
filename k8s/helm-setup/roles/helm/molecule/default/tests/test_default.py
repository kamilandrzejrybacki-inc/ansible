"""Testinfra tests for helm role."""


def test_helm_binary_exists(host):
    """Verify helm binary exists at the expected path."""
    helm = host.file("/usr/local/bin/helm")
    assert helm.exists
    assert helm.mode & 0o111 != 0


def test_helm_runs(host):
    """Verify helm can report its version."""
    result = host.run("helm version --short")
    assert result.rc == 0
    assert "v3" in result.stdout
