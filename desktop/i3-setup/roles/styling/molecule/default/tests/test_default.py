"""Testinfra tests for styling role."""


def test_xresources_accent_color(host):
    """Verify accent color is patched in .Xresources."""
    content = host.file("/tmp/test-dotfiles/.Xresources").content_string
    assert "#a7c080" in content


def test_xresources_bg_color(host):
    """Verify background color is patched in .Xresources."""
    content = host.file("/tmp/test-dotfiles/.Xresources").content_string
    assert "#2e383c" in content


def test_xresources_fg_color(host):
    """Verify foreground color is patched in .Xresources."""
    content = host.file("/tmp/test-dotfiles/.Xresources").content_string
    assert "#d3c6aa" in content


def test_i3_inner_gap(host):
    """Verify i3 inner gap is patched."""
    content = host.file("/tmp/test-dotfiles/.config/i3/config").content_string
    assert "gaps inner 10" in content


def test_i3_outer_gap(host):
    """Verify i3 outer gap is patched."""
    content = host.file("/tmp/test-dotfiles/.config/i3/config").content_string
    assert "gaps outer 5" in content


def test_i3_border_width(host):
    """Verify i3 border width is patched."""
    content = host.file("/tmp/test-dotfiles/.config/i3/config").content_string
    assert "default_border pixel 2" in content


def test_kitty_font_size(host):
    """Verify kitty font size is patched."""
    content = host.file(
        "/tmp/test-dotfiles/.config/kitty/kitty.conf"
    ).content_string
    assert "font_size 11" in content
