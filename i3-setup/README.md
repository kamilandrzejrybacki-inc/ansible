# i3-setup

Ansible playbooks for installing and configuring an i3wm desktop environment themed around [Everforest Dark](https://github.com/sainnhe/everforest).

Dotfiles are sourced from [kamilrybacki/dotfiles](https://github.com/kamilrybacki/dotfiles).

## Playbooks

### `dotfiles.yml` — Full install

Installs all packages, builds i3lock-color from source, installs fastfetch, and symlinks the dotfiles into `$HOME`.

```bash
ansible-playbook i3-setup/dotfiles.yml \
  -i i3-setup/inventory/localhost.ini \
  --ask-become-pass
```

### `styling.yml` — Visual customization

Interactively prompts for colors, gap sizes, font size, and border width, then patches the relevant config files and reloads i3 and Xresources live.

```bash
ansible-playbook i3-setup/styling.yml \
  -i i3-setup/inventory/localhost.ini
```

## Roles

| Role | What it does |
|---|---|
| `packages` | Installs all apt packages (i3, polybar, rofi, dunst, kitty, zsh, and more) |
| `dotfiles` | Clones `kamilrybacki/dotfiles` and symlinks configs into `$HOME` |
| `i3lock_color` | Builds [i3lock-color](https://github.com/Raymo111/i3lock-color) from source via autotools |
| `fastfetch` | Installs the latest [fastfetch](https://github.com/fastfetch-cli/fastfetch) release from GitHub |
| `styling` | Patches `.Xresources`, `i3/config`, and `kitty.conf` with custom values |

## Styling options

When running `styling.yml` you will be prompted for:

| Option | Default | Affects |
|---|---|---|
| Accent color | `#a7c080` | `.Xresources` `green` variable |
| Background color | `#2e383c` | `.Xresources` `bg0` variable |
| Foreground color | `#d3c6aa` | `.Xresources` `fg` variable |
| i3 inner gap | `10` px | `i3/config` |
| i3 outer gap | `5` px | `i3/config` |
| Terminal font size | `11` pt | `kitty.conf` |
| Border width | `2` px | `i3/config` |

Press Enter at any prompt to keep the current value.

## Structure

```
i3-setup/
├── dotfiles.yml
├── styling.yml
├── inventory/
│   └── localhost.ini
├── group_vars/
│   └── all.yml          ← shared vars (dotfiles_dest)
└── roles/
    ├── packages/
    ├── dotfiles/
    ├── i3lock_color/
    ├── fastfetch/
    └── styling/
```
