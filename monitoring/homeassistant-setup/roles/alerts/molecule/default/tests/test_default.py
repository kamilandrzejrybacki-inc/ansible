"""Testinfra tests for homeassistant alerts role."""


def test_automations_yaml_created(host):
    """Verify automations.yaml is created."""
    automations = host.file("/tmp/test-ha-config/automations.yaml")
    assert automations.exists
    assert automations.is_file
    assert automations.mode == 0o644


def test_automations_has_cpu_alert(host):
    """Verify high CPU alert automation exists."""
    content = host.file("/tmp/test-ha-config/automations.yaml").content_string
    assert "alert_high_cpu" in content
    assert "90" in content


def test_automations_has_disk_alert(host):
    """Verify high disk alert automation exists."""
    content = host.file("/tmp/test-ha-config/automations.yaml").content_string
    assert "alert_high_disk" in content
    assert "85" in content


def test_automations_has_http_service_alert(host):
    """Verify HTTP service down alert exists."""
    content = host.file("/tmp/test-ha-config/automations.yaml").content_string
    assert "alert_n8n_down" in content


def test_automations_has_ping_service_alert(host):
    """Verify ping service unreachable alert exists."""
    content = host.file("/tmp/test-ha-config/automations.yaml").content_string
    assert "alert_router_unreachable" in content


def test_automations_has_docker_service_alert(host):
    """Verify docker container stopped alert exists."""
    content = host.file("/tmp/test-ha-config/automations.yaml").content_string
    assert "alert_gitea_stopped" in content


def test_configuration_has_automation_include(host):
    """Verify configuration.yaml includes automations."""
    content = host.file("/tmp/test-ha-config/configuration.yaml").content_string
    assert "automation:" in content
