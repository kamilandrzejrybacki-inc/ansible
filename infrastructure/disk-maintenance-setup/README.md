# disk-maintenance-setup

Keeps the homelab's usual disk hogs bounded automatically. Idempotent.

```bash
ansible-playbook -i inventory setup.yml
```

- **journald cap** (`SystemMaxUse=500M`) → all hosts (lw-main, lw-c1/c2/c3, lw-nas).
- **weekly docker-prune timer** (Sun 04:00 → `docker builder/image prune -af --filter until=168h`)
  → `docker_hosts` only (lw-main edge). No docker restart. k3s nodes self-GC images via kubelet.

Tune in `group_vars/all.yml`. First applied manually 2026-06-22 (lw-main had filled to 98% from
Docker build cache); this codifies it so a host re-provision restores it.
