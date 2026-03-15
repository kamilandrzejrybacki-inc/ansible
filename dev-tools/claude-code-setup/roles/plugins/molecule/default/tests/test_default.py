"""Testinfra tests for plugins role."""


def test_claude_cli_exists(host):
    """Verify mock claude CLI is available."""
    claude = host.file("/usr/local/bin/claude")
    assert claude.exists
    assert claude.mode == 0o755


def test_marketplace_registered(host):
    """Verify marketplace was registered."""
    result = host.run("claude plugins marketplace list")
    assert result.rc == 0
    assert "obra/superpowers-marketplace" in result.stdout


def test_plugins_installed(host):
    """Verify plugins were installed."""
    result = host.run("claude plugins list")
    assert result.rc == 0
    assert "superpowers@claude-plugins-official" in result.stdout
    assert "context7@claude-plugins-official" in result.stdout


def test_blocked_plugin_disabled(host):
    """Verify blocked plugin was disabled."""
    result = host.run("claude plugins list")
    assert result.rc == 0
    assert "code-review@claude-plugins-official" not in result.stdout
