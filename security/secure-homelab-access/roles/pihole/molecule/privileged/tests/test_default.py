"""Testinfra tests for pihole role."""


def test_pihole_container_running(host):
    """Verify the Pi-hole container is running."""
    result = host.run("docker ps --filter name=pihole --format '{{.Status}}'")
    assert "Up" in result.stdout


def test_pihole_dns_port_listening(host):
    """Verify Pi-hole is listening on DNS port 53."""
    socket = host.socket("tcp://0.0.0.0:53")
    assert socket.is_listening


def test_pihole_data_directory_exists(host):
    """Verify the Pi-hole data directories were created."""
    assert host.file("/opt/homelab/pihole/etc-pihole").is_directory
    assert host.file("/opt/homelab/pihole/etc-dnsmasq.d").is_directory


def test_pihole_network_connected(host):
    """Verify Pi-hole is connected to the homelab network."""
    result = host.run(
        "docker inspect pihole --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}'"
    )
    assert "homelab-net" in result.stdout
