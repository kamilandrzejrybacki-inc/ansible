"""Testinfra tests for serena role."""


def test_pipx_installed(host):
    """Verify pipx is installed."""
    result = host.run("which pipx")
    assert result.rc == 0


def test_uv_installed(host):
    """Verify uv is available on PATH."""
    result = host.run("uv --version")
    assert result.rc == 0


def test_serena_config_directory_exists(host):
    """Verify Serena config directory was created."""
    config_dir = host.file("/root/.serena")
    assert config_dir.exists
    assert config_dir.is_directory


def test_serena_config_file_exists(host):
    """Verify Serena config file was deployed."""
    config_file = host.file("/root/.serena/serena_config.yml")
    assert config_file.exists
