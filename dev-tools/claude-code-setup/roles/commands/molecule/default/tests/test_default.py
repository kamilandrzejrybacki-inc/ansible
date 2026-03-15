"""Testinfra tests for commands role."""


def test_commands_directory_exists(host):
    """Verify commands directory is created."""
    commands_dir = host.file("/tmp/test-claude-commands")
    assert commands_dir.exists
    assert commands_dir.is_directory
    assert commands_dir.mode == 0o755


def test_serena_onboard_command_deployed(host):
    """Verify serena-onboard command file is deployed."""
    cmd_file = host.file("/tmp/test-claude-commands/serena-onboard.md")
    assert cmd_file.exists
    assert cmd_file.is_file
    assert cmd_file.mode == 0o644


def test_serena_onboard_content(host):
    """Verify command file contains expected content."""
    content = host.file(
        "/tmp/test-claude-commands/serena-onboard.md"
    ).content_string
    assert "Serena" in content
