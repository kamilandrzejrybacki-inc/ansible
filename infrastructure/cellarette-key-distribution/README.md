# cellarette-key-distribution

Distributes the `cellarette-ssh` Kubernetes secret's public key to every homelab node's `kamil` user `authorized_keys`.

## Why

The Cellarette `ssh` cli_passthrough tool uses a dedicated keypair stored in the `cellarette-ssh` k8s secret (cellarette namespace). The matching public key must be in `~kamil/.ssh/authorized_keys` on every target node, otherwise the tool returns `Permission denied (publickey)`.

`lw-main` has two user accounts:
- `kamil-rybacki` — admin login (matches the SSH key in this repo)
- `kamil` — operator account, same UID layout as the other homelab nodes

The ssh config inside the cellarette pod maps `lw-* 192.168.0.*` → `User kamil`, so the key has to land in `/home/kamil/.ssh/authorized_keys` on lw-main too.

## Run

```bash
ansible-playbook infrastructure/cellarette-key-distribution/setup.yml \
  -i infrastructure/cellarette-key-distribution/inventory/hosts.ini \
  --ask-become-pass
```

`--ask-become-pass` is required because we sudo to write `/home/kamil/.ssh/authorized_keys` on `lw-main` (we authenticate as `kamil-rybacki` there, not `kamil`).

## Re-key

If the cellarette-ssh secret is rotated (new keypair), re-run the playbook. It is idempotent — `ansible.posix.authorized_key` only adds the key if it isn't already present, but does NOT remove old keys. Manually delete stale `cellarette@homelab` lines first if rotating.
