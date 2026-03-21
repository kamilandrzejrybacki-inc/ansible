"""Testinfra tests for bambulab dashboard role."""


def test_dashboards_directory(host):
    """Verify dashboards directory exists."""
    d = host.file("/tmp/test-ha-config/dashboards")
    assert d.exists
    assert d.is_directory


def test_bambulab_dashboard_deployed(host):
    """Verify BambuLab dashboard YAML is deployed."""
    dashboard = host.file("/tmp/test-ha-config/dashboards/bambulab.yaml")
    assert dashboard.exists
    assert dashboard.is_file
    assert dashboard.mode == 0o644


def test_dashboard_contains_printer_entities(host):
    """Verify dashboard contains printer sensor entities."""
    content = host.file(
        "/tmp/test-ha-config/dashboards/bambulab.yaml"
    ).content_string
    assert "sensor.x1c_print_status" in content
    assert "sensor.x1c_nozzle_temperature" in content
    assert "camera.x1c_camera" in content


def test_dashboard_contains_ams_slots(host):
    """Verify dashboard contains AMS slot entities."""
    content = host.file(
        "/tmp/test-ha-config/dashboards/bambulab.yaml"
    ).content_string
    assert "sensor.x1c_tray_1_type" in content
    assert "sensor.x1c_tray_4_type" in content


def test_configuration_has_bambulab_dashboard(host):
    """Verify configuration.yaml has BambuLab dashboard entry."""
    content = host.file("/tmp/test-ha-config/configuration.yaml").content_string
    assert "bambulab:" in content
    assert "dashboards/bambulab.yaml" in content
