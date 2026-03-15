"""Testinfra tests for dotfiles role."""


def test_dotfiles_cloned(host):
    """Verify dotfiles repository was cloned."""
    dotfiles_dir = host.file("/tmp/test-dotfiles")
    assert dotfiles_dir.exists
    assert dotfiles_dir.is_directory


def test_dotfiles_git_repo(host):
    """Verify cloned directory is a git repository."""
    git_dir = host.file("/tmp/test-dotfiles/.git")
    assert git_dir.exists
    assert git_dir.is_directory


def test_xresources_symlink(host):
    """Verify .Xresources symlink is created."""
    link = host.file("/root/.Xresources")
    assert link.exists
    assert link.is_symlink
    assert link.linked_to == "/tmp/test-dotfiles/.Xresources"


def test_i3_config_symlink(host):
    """Verify .config/i3/config symlink is created."""
    link = host.file("/root/.config/i3/config")
    assert link.exists
    assert link.is_symlink
    assert link.linked_to == "/tmp/test-dotfiles/.config/i3/config"


def test_i3_parent_directory(host):
    """Verify parent directory for i3 config was created."""
    parent = host.file("/root/.config/i3")
    assert parent.exists
    assert parent.is_directory
