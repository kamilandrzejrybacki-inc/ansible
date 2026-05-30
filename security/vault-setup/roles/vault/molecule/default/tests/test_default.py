"""Testinfra tests for vault role."""


def test_vault_directories(host):
    """Verify Vault directories were created."""
    for d in ["/opt/vault", "/opt/vault/data", "/opt/vault/config", "/opt/vault/logs"]:
        directory = host.file(d)
        assert directory.exists
        assert directory.is_directory
        assert directory.mode == 0o700


def test_vault_config(host):
    """Verify the Vault HCL config was written."""
    f = host.file("/opt/vault/config/vault.hcl")
    assert f.exists
    assert f.mode == 0o644


def test_vault_compose(host):
    """Verify the docker-compose.yml was written."""
    f = host.file("/opt/vault/docker-compose.yml")
    assert f.exists
    assert f.mode == 0o644
