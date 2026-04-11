"""Testinfra tests for rtk role."""
import json


def test_rtk_installed(host):
    """Verify rtk binary is installed."""
    result = host.run("rtk --version")
    assert result.rc == 0


def test_rtk_hook_script_exists(host):
    """Verify rtk Claude Code hook script was created."""
    hook = host.file("/root/.claude/hooks/rtk-rewrite.sh")
    assert hook.exists


def test_rtk_hook_skip_rules_present(host):
    """Verify ANSIBLE MANAGED RTK SKIP RULES block was injected."""
    hook = host.file("/root/.claude/hooks/rtk-rewrite.sh")
    content = hook.content_string
    assert "BEGIN ANSIBLE MANAGED RTK SKIP RULES" in content
    assert "ansible-playbook" in content
    assert "helm" in content
    assert "docker compose logs" in content or "docker\\ compose\\ logs" in content


def test_rtk_hook_in_settings(host):
    """Verify rtk PreToolUse hook is present in Claude Code settings.json."""
    settings_file = host.file("/root/.claude/settings.json")
    assert settings_file.exists
    settings = json.loads(settings_file.content_string)
    pre_tool_use = settings.get("hooks", {}).get("PreToolUse", [])
    bash_hooks = [h for h in pre_tool_use if h.get("matcher") == "Bash"]
    assert len(bash_hooks) > 0
    commands = [c["command"] for c in bash_hooks[0].get("hooks", [])]
    assert any("rtk-rewrite.sh" in cmd for cmd in commands)
