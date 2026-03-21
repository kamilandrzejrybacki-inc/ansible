"""Testinfra tests for homeassistant monitoring role."""


def test_configuration_yaml_exists(host):
    """Verify configuration.yaml is deployed."""
    config = host.file("/tmp/test-ha-config/configuration.yaml")
    assert config.exists
    assert config.is_file
    assert config.mode == 0o644


def test_configuration_has_system_monitor(host):
    """Verify system monitoring resources are configured."""
    content = host.file("/tmp/test-ha-config/configuration.yaml").content_string
    assert "systemmonitor" in content
    assert "processor_use" in content
    assert "memory_use_percent" in content
    assert "disk_use_percent" in content


def test_configuration_has_uptime_sensor(host):
    """Verify uptime sensor is configured."""
    content = host.file("/tmp/test-ha-config/configuration.yaml").content_string
    assert "platform: uptime" in content


def test_configuration_has_http_service(host):
    """Verify HTTP service monitoring is configured."""
    content = host.file("/tmp/test-ha-config/configuration.yaml").content_string
    assert "n8n Status" in content
    assert "http://192.168.1.10:5678/healthz" in content


def test_configuration_has_ping_service(host):
    """Verify ping service monitoring is configured."""
    content = host.file("/tmp/test-ha-config/configuration.yaml").content_string
    assert "platform: ping" in content
    assert "192.168.1.1" in content


def test_configuration_has_docker_service(host):
    """Verify Docker container monitoring is configured."""
    content = host.file("/tmp/test-ha-config/configuration.yaml").content_string
    assert "gitea" in content
    assert "command_line:" in content


def test_configuration_has_webhook(host):
    """Verify webhook alerting endpoint is configured."""
    content = host.file("/tmp/test-ha-config/configuration.yaml").content_string
    assert "webhook_alert" in content
    assert "https://hooks.example.com/test-webhook" in content
