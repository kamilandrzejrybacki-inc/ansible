"""Testinfra tests for swe_af role."""


def test_swe_af_directory_exists(host):
    """Verify the SWE-AF installation directory was created."""
    d = host.file("/opt/swe-af")
    assert d.exists
    assert d.is_directory


def test_swe_af_env_file(host):
    """Verify .env file was created with restricted permissions."""
    f = host.file("/opt/swe-af/.env")
    assert f.exists
    assert f.mode == 0o600


def test_swe_af_venv_exists(host):
    """Verify the Python virtual environment was created."""
    f = host.file("/opt/swe-af/.venv/bin/activate")
    assert f.exists


def test_swe_af_pip_packages(host):
    """Verify SWE-AF package is installed in the venv."""
    result = host.run("/opt/swe-af/.venv/bin/pip show swe-af")
    assert result.rc == 0
