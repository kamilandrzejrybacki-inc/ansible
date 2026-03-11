# i3-Setup Ansible Playbooks — Design Spec

**Date:** 2026-03-11
**Status:** Approved

---

## Overview

A local Ansible repository at `~/Code/ansible/` for quickly spinning up a Linux desktop environment. The first playbook set, `i3-setup`, installs and configures an i3wm/Everforest Dark desktop by:

1. Installing all required system packages via `apt`
2. Building `i3lock-color` from source
3. Installing `fastfetch` from GitHub releases
4. Cloning `github.com/kamilrybacki/dotfiles` and symlinking all configs natively via Ansible

A companion `styling.yml` playbook allows interactive visual customization (colors, gaps, font sizes) at any time, independently of the install flow.

---

## Repository Structure

```
ansible/
└── i3-setup/
    ├── dotfiles.yml          # Main install playbook
    ├── styling.yml           # Standalone styling playbook
    ├── inventory/
    │   └── localhost.ini     # Targets localhost
    └── roles/
        ├── packages/         # apt package installation
        ├── dotfiles/         # git clone + symlink management
        ├── i3lock_color/     # Build i3lock-color from source
        ├── fastfetch/        # Install fastfetch from GitHub releases
        └── styling/          # Patch config files + reload
```

Future playbooks live in their own sibling folders under `ansible/`.

---

## Playbooks

### `dotfiles.yml`

Runs against `localhost`. Role execution order:

1. `packages` — installs all apt dependencies
2. `i3lock_color` — builds and installs i3lock-color
3. `fastfetch` — fetches and installs latest release `.deb`
4. `dotfiles` — clones repo and creates symlinks

### `styling.yml`

Standalone playbook, run independently whenever visual tweaks are desired. Uses `vars_prompt` to collect values interactively, then applies them via the `styling` role.

---

## Roles

### `packages`

- **Privilege:** `become: true`
- Runs `apt update` then installs all packages in one task
- Package list defined in `defaults/main.yml` for easy maintenance

**Package list:**
```yaml
packages:
  - i3
  - polybar
  - rofi
  - dunst
  - kitty
  - zsh
  - nitrogen
  - xss-lock
  - feh
  - pulseaudio-utils
  - papirus-icon-theme
  - python3-pil
  # i3lock-color build dependencies
  - build-essential
  - cmake
  - pkg-config
  - libpam0g-dev
  - libxcb-xkb-dev
  - libxcb-xrm-dev
  - libxkbcommon-dev
  - libxkbcommon-x11-dev
  - libgif-dev
```

---

### `dotfiles`

- **Privilege:** runs as current user
- Clones `https://github.com/kamilrybacki/dotfiles.git` with `update: yes` (idempotent — pulls latest on re-runs)
- Loops over a symlink map defined in `defaults/main.yml`, creates parent directories, then creates symlinks using `ansible.builtin.file` with `state: link`
- Existing regular files are backed up with `.bak` suffix before symlinking

**Symlink map** (mirrors `install.sh` exactly):
```yaml
dotfiles_repo: "https://github.com/kamilrybacki/dotfiles.git"
dotfiles_dest: "{{ ansible_env.HOME }}/dotfiles"

dotfiles_links:
  - src: ".Xresources"
  - src: ".zshrc"
  - src: ".config/i3/config"
  - src: ".config/polybar/config.ini"
  - src: ".config/polybar/launch.sh"
  - src: ".config/rofi/config.rasi"
  - src: ".config/rofi/everforest.rasi"
  - src: ".config/dunst/dunstrc"
  - src: ".config/kitty/kitty.conf"
  - src: ".config/kitty/everforest.conf"
  - src: ".config/fastfetch/config.jsonc"
  - src: ".local/bin/lock.sh"
```

After symlinking, sets executable bit on `lock.sh` and `launch.sh`.

---

### `i3lock_color`

- **Privilege:** `become: true` for `make install`
- Idempotent: checks for `/usr/local/bin/i3lock` before doing any work
- If not present:
  1. Clones `https://github.com/Raymo111/i3lock-color.git` to a temp directory
  2. Runs `cmake`, `make`, `make install`
  3. Cleans up the temp build directory

---

### `fastfetch`

- **Privilege:** `become: true` for `apt install`
- Queries the GitHub API for the latest release tag
- Downloads `fastfetch-linux-amd64.deb` to `/tmp/`
- Installs with `ansible.builtin.apt` (`deb:` parameter)
- Cleans up the `.deb` file after install

---

### `styling`

- **Privilege:** runs as current user; `xrdb` and `i3-msg` also run as current user
- Patches config files in-place using `ansible.builtin.replace`
- After all patches, reloads:
  - `xrdb ~/.Xresources` — applies color palette live
  - `i3-msg reload` — applies i3 config without logout

**Exposed options (with Everforest Dark defaults):**

| Option | Patches | Default |
|---|---|---|
| Accent color (hex) | `.Xresources` — `green` variable | `#a7c080` |
| Background color (hex) | `.Xresources` — `bg0` variable | `#2e383c` |
| Foreground/text color (hex) | `.Xresources` — `fg` variable | `#d3c6aa` |
| i3 inner gap (px) | `.config/i3/config` — `gaps inner` | `10` |
| i3 outer gap (px) | `.config/i3/config` — `gaps outer` | `5` |
| Terminal font size (pt) | `.config/kitty/kitty.conf` — `font_size` | `12` |
| i3 border width (px) | `.config/i3/config` — `default_border` | `2` |

**Note:** Border radius is not supported natively by i3wm and requires a compositor (e.g., picom). It is out of scope for this playbook set.

---

## Design Decisions

- **No `install.sh` dependency:** Ansible manages all symlinks natively via `ansible.builtin.file`, making the playbook fully self-contained and idempotent.
- **Roles scoped to `i3-setup/`:** Roles live under `i3-setup/roles/` rather than a top-level `roles/` directory. They can be promoted to shared roles later if other playbooks need them.
- **Styling decoupled from install:** `styling.yml` is a separate playbook so install and customization concerns don't mix. Re-applying styling never re-runs package installs or symlink creation.
- **Idempotency throughout:** Every role is safe to re-run. `i3lock_color` checks for the binary, `fastfetch` installs via apt (idempotent by default), `dotfiles` uses `git update: yes` and `file state: link`.
