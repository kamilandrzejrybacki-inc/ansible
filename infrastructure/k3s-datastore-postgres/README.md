# k3s-datastore-postgres

IaC for the **k3s control-plane datastore Postgres** — the `k3s_state` database k3s
uses via `--datastore-endpoint`. The container (`k3s-postgres` on `192.168.0.115`)
was previously hand-run with a bare `docker run` and tracked nowhere; this role
captures its exact spec via `community.docker.docker_container`.

## Apply

```bash
cd infrastructure/k3s-datastore-postgres
ansible-playbook setup.yml --check --diff   # ALWAYS dry-run first
ansible-playbook setup.yml                  # real apply
```

As of 2026-05-31 the spec matches the live container, so a real apply is a **no-op**
(`changed=0`). `published_ports`/`volumes` are excluded from the idempotence
comparison (the hand-created container reports `HostIp:""` ≡ `0.0.0.0` and a bind
without the `:rw` suffix — equivalent, but they'd otherwise trigger a spurious
recreate); their values are still applied on create. `image`/`command`/`env`/
`restart_policy` stay strict, so a real tuning or image change IS detected.

## ⚠️ Restart risk

If `--check` ever reports **changed**, a real apply will **recreate** the container
→ the k3s API↔datastore link drops ~3-5 s and the kube-vip control-plane VIP
(`192.168.0.60`) fails over (~1 min of `kubectl: no route to host`). Workloads keep
running; control-plane ops pause. Recreate only in a maintenance window.

## Tuning

`max_connections` was raised 200→300 on 2026-05-31 (the 200 ceiling was hit under
bursty load, stalling the datastore link and causing lockstep kube-vip/nfs
restarts). The `-c` flags here override `postgresql.auto.conf`, so this file is the
single source of truth for those settings.

## Rollback

The pre-bump container is kept renamed `k3s-postgres-pre300` on the host until
pruned: `docker rm k3s-postgres && docker rename k3s-postgres-pre300 k3s-postgres
&& docker start k3s-postgres`.

## From-scratch rebuild

`POSTGRES_PASSWORD` is not managed here (ignored once the data volume is
initialized). For an empty-volume rebuild, pass it once:
`ansible-playbook setup.yml -e k3s_pg_init_password=<superuser-pw>`.
