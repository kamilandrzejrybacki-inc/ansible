"""Testinfra tests for homepage role."""


def test_homepage_container_running(host):
    """Verify the Homepage container is running."""
    result = host.run("docker ps --filter name=homepage --format '{{.Status}}'")
    assert "Up" in result.stdout


def test_homepage_data_directory_exists(host):
    """Verify the Homepage data directory was created."""
    assert host.file("/opt/homelab/homepage").is_directory


def test_homepage_config_files_exist(host):
    """Verify Homepage configuration files were deployed."""
    for config in ["services.yaml", "settings.yaml", "bookmarks.yaml", "widgets.yaml"]:
        f = host.file("/opt/homelab/homepage/" + config)
        assert f.exists
        assert f.mode == 0o644


def test_homepage_network_connected(host):
    """Verify Homepage is connected to the homelab network."""
    result = host.run(
        "docker inspect homepage --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}'"
    )
    assert "homelab-net" in result.stdout
