"""Testinfra tests for claude_config role."""


def test_claude_config_dir_exists(host):
    """Verify Claude config directory is created."""
    config_dir = host.file("/tmp/test-claude-config")
    assert config_dir.exists
    assert config_dir.is_directory


def test_settings_json_deployed(host):
    """Verify settings.json is copied to config directory."""
    settings = host.file("/tmp/test-claude-config/settings.json")
    assert settings.exists
    assert settings.is_file
    assert settings.mode == 0o644


def test_settings_json_content(host):
    """Verify settings.json contains expected content."""
    content = host.file("/tmp/test-claude-config/settings.json").content_string
    assert "permissions" in content


def test_rules_directory_deployed(host):
    """Verify rules directory is copied."""
    rules_dir = host.file("/tmp/test-claude-config/rules")
    assert rules_dir.exists
    assert rules_dir.is_directory


def test_rules_file_exists(host):
    """Verify at least one rules file was copied."""
    rule_file = host.file("/tmp/test-claude-config/rules/coding-style.md")
    assert rule_file.exists
    assert rule_file.is_file


def test_skills_directory_deployed(host):
    """Verify vendored skills directory is copied."""
    skills_dir = host.file("/tmp/test-claude-config/skills")
    assert skills_dir.exists
    assert skills_dir.is_directory


def test_thermo_nuclear_skill_deployed(host):
    """Verify the thermo-nuclear code-quality-review skill is deployed."""
    skill = host.file(
        "/tmp/test-claude-config/skills/"
        "thermo-nuclear-code-quality-review/SKILL.md"
    )
    assert skill.exists
    assert skill.is_file
    assert "thermo-nuclear-code-quality-review" in skill.content_string
