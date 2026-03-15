# ansible

Personal Ansible playbooks for quickly spinning up a local Linux environment.

Each playbook set lives in its own subdirectory and is fully self-contained — inventory, roles, and variables are scoped locally rather than shared globally.

## Playbook sets

| Directory | Description |
|---|---|
| [`i3-setup/`](./i3-setup/) | i3wm desktop environment — packages, dotfiles, i3lock-color, fastfetch, styling |
| [`claude-n8n-setup/`](./claude-n8n-setup/) | Claude Code + n8n MCP integration — Docker, n8n, Claude MCP configuration |
| [`kind-setup/`](./kind-setup/) | Local Kubernetes provisioning — Docker, kind, kubectl, multi-node cluster |

## Usage

```bash
# Install Ansible (one-time)
sudo apt install -y ansible

# Run a playbook
ansible-playbook <playbook-set>/<playbook>.yml \
  -i <playbook-set>/inventory/localhost.ini \
  --ask-become-pass
```

## Structure

```
ansible/
└── <playbook-set>/
    ├── <playbook>.yml
    ├── inventory/
    │   └── localhost.ini
    ├── group_vars/
    │   └── all.yml
    └── roles/
        └── <role>/
            ├── meta/main.yml
            ├── defaults/main.yml
            └── tasks/main.yml
```
