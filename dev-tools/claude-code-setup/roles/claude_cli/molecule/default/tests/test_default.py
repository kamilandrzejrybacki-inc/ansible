"""Testinfra tests for claude_cli role."""


def test_nodejs_installed(host):
    """Verify Node.js is installed."""
    result = host.run("node --version")
    assert result.rc == 0
    major = int(result.stdout.strip().lstrip("v").split(".")[0])
    assert major >= 18


def test_npm_installed(host):
    """Verify npm is installed."""
    result = host.run("npm --version")
    assert result.rc == 0


def test_claude_binary_exists(host):
    """Verify claude CLI binary is available on PATH."""
    result = host.run("which claude")
    assert result.rc == 0


def test_claude_runs(host):
    """Verify claude CLI can report its version."""
    result = host.run("claude --version")
    assert result.rc == 0
