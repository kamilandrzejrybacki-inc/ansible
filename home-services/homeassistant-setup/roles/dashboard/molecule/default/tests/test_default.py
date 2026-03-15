"""Testinfra tests for homeassistant dashboard role."""


def test_dashboards_directory(host):
    """Verify dashboards directory exists."""
    d = host.file("/tmp/test-ha-config/dashboards")
    assert d.exists
    assert d.is_directory


def test_monitoring_dashboard_deployed(host):
    """Verify monitoring dashboard YAML is deployed."""
    dashboard = host.file("/tmp/test-ha-config/dashboards/monitoring.yaml")
    assert dashboard.exists
    assert dashboard.is_file
    assert dashboard.mode == 0o644


def test_dashboard_has_system_gauges(host):
    """Verify dashboard contains system monitoring gauges."""
    content = host.file(
        "/tmp/test-ha-config/dashboards/monitoring.yaml"
    ).content_string
    assert "sensor.processor_use" in content
    assert "sensor.memory_use_percent" in content
    assert "sensor.disk_use_percent" in content


def test_dashboard_has_service_entities(host):
    """Verify dashboard contains monitored service entities."""
    content = host.file(
        "/tmp/test-ha-config/dashboards/monitoring.yaml"
    ).content_string
    assert "sensor.n8n_status" in content
    assert "binary_sensor.router" in content
    assert "sensor.gitea_container" in content


def test_configuration_has_lovelace_block(host):
    """Verify configuration.yaml has Lovelace dashboards block."""
    content = host.file("/tmp/test-ha-config/configuration.yaml").content_string
    assert "lovelace:" in content
    assert "dashboards/monitoring.yaml" in content
