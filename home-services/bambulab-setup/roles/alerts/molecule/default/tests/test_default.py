"""Testinfra tests for bambulab alerts role."""


def test_configuration_yaml_has_webhook(host):
    """Verify webhook rest_command is added to configuration.yaml."""
    content = host.file("/tmp/test-ha-config/configuration.yaml").content_string
    assert "bambulab_webhook_alert" in content
    assert "https://hooks.example.com/test-webhook" in content


def test_automations_yaml_created(host):
    """Verify automations.yaml is created."""
    automations = host.file("/tmp/test-ha-config/automations.yaml")
    assert automations.exists
    assert automations.is_file


def test_automations_has_print_completed(host):
    """Verify print completed automation exists."""
    content = host.file("/tmp/test-ha-config/automations.yaml").content_string
    assert "bambulab_x1c_print_completed" in content


def test_automations_has_print_failed(host):
    """Verify print failed automation exists."""
    content = host.file("/tmp/test-ha-config/automations.yaml").content_string
    assert "bambulab_x1c_print_failed" in content


def test_automations_has_filament_runout(host):
    """Verify filament runout automations exist for AMS slots."""
    content = host.file("/tmp/test-ha-config/automations.yaml").content_string
    assert "bambulab_x1c_filament_runout_slot1" in content
    assert "bambulab_x1c_filament_runout_slot4" in content


def test_automation_include_directive(host):
    """Verify automation include directive is in configuration.yaml."""
    content = host.file("/tmp/test-ha-config/configuration.yaml").content_string
    assert "automation:" in content
