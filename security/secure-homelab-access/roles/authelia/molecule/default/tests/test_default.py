"""Testinfra tests for authelia role."""


def test_authelia_container_running(host):
    """Verify the Authelia container is running."""
    result = host.run("docker ps --filter name=authelia --format '{{.Status}}'")
    assert "Up" in result.stdout


def test_authelia_data_directory_exists(host):
    """Verify the Authelia data directories were created."""
    assert host.file("/opt/homelab/authelia").is_directory
    assert host.file("/opt/homelab/authelia/config").is_directory


def test_authelia_config_files_exist(host):
    """Verify Authelia configuration files were deployed."""
    config = host.file("/opt/homelab/authelia/config/configuration.yml")
    assert config.exists
    assert config.mode == 0o600
    users = host.file("/opt/homelab/authelia/config/users_database.yml")
    assert users.exists
    assert users.mode == 0o600


def test_authelia_network_connected(host):
    """Verify Authelia is connected to the homelab network."""
    result = host.run(
        "docker inspect authelia --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}'"
    )
    assert "homelab-net" in result.stdout
