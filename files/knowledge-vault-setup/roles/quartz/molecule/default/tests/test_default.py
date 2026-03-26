"""Testinfra tests for quartz role."""


def test_quartz_data_directory_exists(host):
    """Verify the Quartz data directory was created."""
    assert host.file("/opt/knowledge-vault/quartz").is_directory


def test_quartz_dockerfile_exists(host):
    """Verify the Dockerfile was templated."""
    dockerfile = host.file("/opt/knowledge-vault/quartz/Dockerfile")
    assert dockerfile.exists


def test_quartz_config_exists(host):
    """Verify quartz.config.ts was templated."""
    config = host.file("/opt/knowledge-vault/quartz/quartz.config.ts")
    assert config.exists
    assert config.contains("Knowledge Vault")


def test_quartz_container_running(host):
    """Verify the Quartz container is running."""
    result = host.run("docker ps --filter name=quartz --format '{{.Status}}'")
    assert "Up" in result.stdout


def test_quartz_port_listening(host):
    """Verify Quartz is listening on port 8080."""
    socket = host.socket("tcp://0.0.0.0:8080")
    assert socket.is_listening


def test_quartz_serves_html(host):
    """Verify Quartz serves HTML content."""
    result = host.run("curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/")
    assert result.stdout.strip() == "200"
