"""Testinfra tests for stirling role."""


def test_stirling_container_running(host):
    """Verify the Stirling-PDF container is running."""
    result = host.run("docker ps --filter name=stirling-pdf --format '{{.Status}}'")
    assert "Up" in result.stdout


def test_stirling_port_listening(host):
    """Verify Stirling-PDF is listening on port 8080."""
    socket = host.socket("tcp://127.0.0.1:8080")
    assert socket.is_listening


def test_stirling_data_directory_exists(host):
    """Verify the Stirling-PDF data directories were created."""
    assert host.file("/opt/stirling-pdf/configs").is_directory
    assert host.file("/opt/stirling-pdf/logs").is_directory
    assert host.file("/opt/stirling-pdf/training-data").is_directory


def test_stirling_health_check(host):
    """Verify Stirling-PDF responds to HTTP requests."""
    result = host.run(
        "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080"
    )
    assert result.stdout in ("200", "302")
