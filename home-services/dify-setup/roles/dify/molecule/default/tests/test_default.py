"""Testinfra tests for dify role."""


def test_dify_directory_exists(host):
    """Verify the Dify installation directory was created."""
    d = host.file("/opt/dify")
    assert d.exists
    assert d.is_directory


def test_dify_docker_dir_exists(host):
    """Verify the docker subdirectory exists."""
    d = host.file("/opt/dify/docker")
    assert d.exists
    assert d.is_directory


def test_dify_env_file(host):
    """Verify .env file was created with restricted permissions."""
    f = host.file("/opt/dify/docker/.env")
    assert f.exists
    assert f.mode == 0o600


def test_dify_env_contains_vector_store(host):
    """Verify .env file contains VECTOR_STORE setting."""
    f = host.file("/opt/dify/docker/.env")
    assert f.contains("VECTOR_STORE=")


def test_dify_env_contains_secret_key(host):
    """Verify .env file contains a generated SECRET_KEY."""
    f = host.file("/opt/dify/docker/.env")
    assert f.contains("SECRET_KEY=")
