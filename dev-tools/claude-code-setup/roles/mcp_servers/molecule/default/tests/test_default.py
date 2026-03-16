"""Testinfra tests for mcp_servers role."""


def test_claude_cli_exists(host):
    """Verify mock claude CLI is available."""
    claude = host.file("/usr/local/bin/claude")
    assert claude.exists
    assert claude.mode == 0o755


def test_claude_cli_executable(host):
    """Verify mock claude CLI can be executed."""
    result = host.run("claude mcp list")
    assert result.rc == 0
    assert "mock claude mcp list" in result.stdout
