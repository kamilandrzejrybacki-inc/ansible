"""Testinfra tests for handy role."""

import pytest


@pytest.mark.parametrize("pkg", [
    "libgtk-layer-shell0",
    "libwebkit2gtk-4.1-0",
    "wget",
])
def test_common_dependency_installed(host, pkg):
    """Verify common dependency packages are installed."""
    package = host.package(pkg)
    assert package.is_installed


def test_x11_tools_installed(host):
    """Verify xdotool is installed for x11 display server."""
    package = host.package("xdotool")
    assert package.is_installed


def test_handy_binary_exists(host):
    """Verify handy binary is available on PATH."""
    result = host.run("which handy")
    assert result.rc == 0
