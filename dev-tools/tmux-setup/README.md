# tmux Setup — Termix Auto-Tmux prerequisite

Installs `tmux` on every homelab host that [Termix](https://termix.site)
connects to over SSH.

## Why

Termix's **Auto-Tmux** (enabled per host in the host's settings) runs
`tmux attach || tmux new` on connect. The remote shell — and anything running in
it, including a Claude Code agent — then lives inside a tmux session on the
target host, so a browser disconnect / tab-out only detaches the view; the
process keeps running and re-attaches on reconnect. This requires the `tmux`
binary present on each target.

## Run

```bash
ansible-playbook dev-tools/tmux-setup/setup.yml \
  -i dev-tools/tmux-setup/inventory/hosts.ini

# targets without passwordless sudo:
ansible-playbook dev-tools/tmux-setup/setup.yml \
  -i dev-tools/tmux-setup/inventory/hosts.ini --ask-become-pass

# a subset:
ansible-playbook dev-tools/tmux-setup/setup.yml \
  -i dev-tools/tmux-setup/inventory/hosts.ini --limit lw-c1,lw-nas
```

Idempotent — safe to re-run. Prints the installed tmux version per host.

## Hosts

Defined in `inventory/hosts.ini` under `[tmux_hosts]`: `lw-main` (local),
`lw-c1`, `lw-c2`, `lw-c3`, `lw-nas`, `lw-pi`. Add or remove hosts there as your
Termix targets change.

## After running

In Termix, open each host's settings and turn on **Auto Tmux** (and optionally
**Enable Tmux Monitor**). New connections then auto-attach to a persistent tmux
session.
