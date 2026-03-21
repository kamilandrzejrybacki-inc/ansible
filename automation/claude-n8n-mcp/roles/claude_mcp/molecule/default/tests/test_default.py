"""Testinfra tests for claude_mcp role."""


def test_claude_cli_exists(host):
    """Verify mock claude CLI is available."""
    claude = host.file("/usr/local/bin/claude")
    assert claude.exists
    assert claude.mode == 0o755


def test_claude_json_created(host):
    """Verify .claude.json was created with MCP server entry."""
    claude_json = host.file("/root/.claude.json")
    assert claude_json.exists
    assert claude_json.is_file


def test_mcp_server_in_config(host):
    """Verify n8n MCP server is registered in Claude config."""
    content = host.file("/root/.claude.json").content_string
    assert "n8n" in content
