# kind-setup

Ansible playbook for provisioning local Kubernetes clusters using [kind](https://kind.sigs.k8s.io/) (Kubernetes in Docker).

Installs Docker, kind, and kubectl, then creates a configurable multi-node cluster on the local machine.

## Prerequisites

- Ansible 2.10+
- Debian/Ubuntu-based system
- `sudo` access

## Usage

```bash
ansible-playbook kind-setup/setup.yml \
  -i kind-setup/inventory/localhost.ini \
  --ask-become-pass
```

## Prompts

| Prompt | Default | Description |
|---|---|---|
| Cluster name | `local-cluster` | Name for the kind cluster |
| Worker nodes | `2` | Number of worker nodes to create |
| API server port | `6443` | Host port for the Kubernetes API server |
| HTTP port | `80` | Host port mapped to the control-plane's port 80 (for ingress) |
| HTTPS port | `443` | Host port mapped to the control-plane's port 443 (for ingress) |

## Roles

| Role | What it does |
|---|---|
| `docker` | Installs Docker engine via the official APT repository (Debian/Ubuntu) |
| `kind` | Downloads the kind binary from GitHub releases and installs kubectl from the Kubernetes APT repository |
| `cluster` | Renders a kind cluster config from a Jinja2 template and creates the cluster |

## Cluster management

```bash
# List clusters
kind get clusters

# Access the cluster
kubectl cluster-info --context kind-local-cluster

# Delete the cluster
kind delete cluster --name local-cluster
```

## Structure

```
kind-setup/
├── setup.yml
├── inventory/
│   └── localhost.ini
├── group_vars/
│   └── all.yml          <- default cluster settings
└── roles/
    ├── docker/
    ├── kind/
    └── cluster/
        └── templates/
            └── kind-config.yml.j2
```
