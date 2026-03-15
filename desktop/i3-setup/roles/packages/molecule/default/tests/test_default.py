"""Testinfra tests for packages role."""

import pytest


@pytest.mark.parametrize("pkg", [
    "zsh",
    "feh",
    "dunst",
])
def test_package_installed(host, pkg):
    """Verify each apt package is installed."""
    package = host.package(pkg)
    assert package.is_installed
