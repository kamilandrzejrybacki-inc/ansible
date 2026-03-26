# lw-c1 Compute Node Setup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provision lw-c1 (192.168.0.107) as a bare-metal K3s compute node running n8n queue workers, GitHub Actions runners, and a vCluster test environment, while migrating n8n on lw-s1 to queue mode.

**Architecture:** K3s installed directly on xUbuntu via Ansible. Workloads (n8n workers, GitHub runners) run as K8s Deployments with secrets sourced from Vault at deploy time. n8n main on lw-s1 is switched to queue mode, pointing at Redis on lw-nas. Existing roles (helm, k9s, headlamp, argocd) are reused on lw-c1 without modification.

**Tech Stack:** Ansible, K3s v1.32, Helm v3, kubernetes.core Ansible collection, vCluster Helm chart, myoung34/github-runner, n8n queue mode (Bull/Redis)

**Spec:** `docs/specs/2026-03-26-lw-c1-compute-node-setup-design.md`

---

## File Map

### New files
| File | Purpose |
|------|---------|
| `k8s/k3s-setup/setup.yml` | Main playbook: install K3s + fetch kubeconfig + deploy management stack |
| `k8s/k3s-setup/inventory/hosts.ini` | lw-c1 as `[compute]` host |
| `k8s/k3s-setup/group_vars/all.yml` | K3s version, kubeconfig path, tool versions |
| `k8s/k3s-setup/ansible.cfg` | roles_path pointing to sibling k8s playbook roles |
| `k8s/k3s-setup/roles/k3s/tasks/main.yml` | Install K3s binary, configure systemd, wait for node ready |
| `k8s/k3s-setup/roles/k3s/defaults/main.yml` | k3s_version, k3s_install_url |
| `k8s/k3s-setup/roles/k3s/meta/main.yml` | Role metadata |
| `k8s/k3s-setup/roles/k3s/molecule/default/molecule.yml` | Molecule test config |
| `k8s/k3s-setup/roles/k3s/molecule/default/converge.yml` | Apply role in molecule |
| `k8s/k3s-setup/roles/k3s/molecule/default/tests/test_k3s.py` | Testinfra: k3s service running, kubectl works |
| `k8s/k3s-setup/roles/kubeconfig/tasks/main.yml` | Fetch kubeconfig, rewrite server address, save locally |
| `k8s/k3s-setup/roles/kubeconfig/defaults/main.yml` | kubeconfig_local_path, k3s_node_ip |
| `k8s/n8n-workers-setup/setup.yml` | Deploy n8n worker Deployment + Secret |
| `k8s/n8n-workers-setup/inventory/localhost.ini` | localhost connection for kubectl |
| `k8s/n8n-workers-setup/group_vars/all.yml` | n8n image version, replica count, Redis/Postgres vars |
| `k8s/n8n-workers-setup/roles/n8n-worker/tasks/main.yml` | Create namespace, apply Secret + Deployment, wait |
| `k8s/n8n-workers-setup/roles/n8n-worker/defaults/main.yml` | n8n_version, replicas, namespace |
| `k8s/n8n-workers-setup/roles/n8n-worker/templates/deployment.yml.j2` | n8n worker Deployment manifest |
| `k8s/n8n-workers-setup/roles/n8n-worker/templates/secret.yml.j2` | n8n worker credentials Secret |
| `k8s/github-runners-setup/setup.yml` | Deploy GitHub runner Deployment + Secret |
| `k8s/github-runners-setup/inventory/localhost.ini` | localhost connection for kubectl |
| `k8s/github-runners-setup/group_vars/all.yml` | runner image, repo, replica count |
| `k8s/github-runners-setup/roles/github-runner/tasks/main.yml` | Create namespace, apply Secret + Deployment, wait |
| `k8s/github-runners-setup/roles/github-runner/defaults/main.yml` | runner_replicas, namespace |
| `k8s/github-runners-setup/roles/github-runner/templates/deployment.yml.j2` | Runner Deployment manifest |
| `k8s/github-runners-setup/roles/github-runner/templates/secret.yml.j2` | Runner PAT Secret |
| `k8s/vcluster-setup/setup.yml` | Deploy vCluster via Helm into test namespace |
| `k8s/vcluster-setup/inventory/localhost.ini` | localhost connection for kubectl |
| `k8s/vcluster-setup/group_vars/all.yml` | vcluster_version, namespace, chart values |
| `k8s/vcluster-setup/roles/vcluster/tasks/main.yml` | Add Helm repo, install vCluster, wait for ready |
| `k8s/vcluster-setup/roles/vcluster/defaults/main.yml` | vcluster chart defaults |

### Modified files
| File | Change |
|------|--------|
| `infrastructure/nas-link-setup/group_vars/all.yml` | Add `192.168.0.107` to `nas_allowed_clients`; add `nodec1_lan_ip` var |
| `infrastructure/nas-link-setup/setup.yml` | Add play targeting `[compute]` with `nas-link-route` role |
| `infrastructure/nas-link-setup/inventory/hosts.ini` | Add lw-c1 to `[compute]` group |
| `automation/n8n-setup/group_vars/all.yml` | Add `n8n_queue_mode`, `n8n_redis_host/port/db` vars (disabled by default) |
| `automation/n8n-setup/roles/n8n/tasks/main.yml` | Add queue mode env vars to `_n8n_env` when `n8n_queue_mode` is true |

---

## Task 1: SSH bootstrap and inventory for lw-c1

**Pre-condition:** You are on the Ansible control node (lw-main or your local machine) and can ping 192.168.0.107.

**Files:**
- Modify: `infrastructure/nas-link-setup/inventory/hosts.ini`
- (All other inventories add lw-c1 per-playbook in later tasks)

- [ ] **Step 1.1: Verify SSH connectivity to lw-c1**

```bash
ssh kamil@192.168.0.107 "echo OK"
```
Expected: `OK` — if this fails, deploy your SSH public key first:
```bash
ssh-copy-id kamil@192.168.0.107
```

- [ ] **Step 1.2: Verify sudo works with homelab pattern**

```bash
ssh kamil@192.168.0.107 "sudo HOME=/home/kamil whoami"
```
Expected: `root`

- [ ] **Step 1.3: Verify Python 3 is available**

```bash
ssh kamil@192.168.0.107 "python3 --version"
```
Expected: `Python 3.x.x`

- [ ] **Step 1.4: Commit**

```bash
git commit --allow-empty -m "chore: verify lw-c1 SSH bootstrap complete"
```

---

## Task 2: NAS networking for lw-c1

**Goal:** Add lw-c1 (192.168.0.107) to NAS DB firewall allowlist and give it a persistent route to 10.0.1.0/24 via lw-main.

**Files:**
- Modify: `infrastructure/nas-link-setup/group_vars/all.yml`
- Modify: `infrastructure/nas-link-setup/setup.yml`
- Modify: `infrastructure/nas-link-setup/inventory/hosts.ini`

- [ ] **Step 2.1: Add lw-c1 to inventory**

Read `infrastructure/nas-link-setup/inventory/hosts.ini`, then add:
```ini
[compute]
lw-c1 ansible_host=192.168.0.107 ansible_user=kamil ansible_python_interpreter=/usr/bin/python3
```

- [ ] **Step 2.2: Add lw-c1 to `nas_allowed_clients` and define `nodec1_lan_ip`**

In `infrastructure/nas-link-setup/group_vars/all.yml`, add under the existing vars:
```yaml
```
Append to `nas_allowed_clients`:
```yaml
  - "192.168.0.107"   # lw-c1 (compute node)
```

- [ ] **Step 2.3: Add lw-c1 play to `nas-link-setup/setup.yml`**

Append to `infrastructure/nas-link-setup/setup.yml`:
```yaml
- name: Add NAS subnet route on lw-c1
  hosts: compute
  become: true
  gather_facts: true
  roles:
    - nas-link-route
```
The `nas-link-route` role uses `node2_lan_ip` but lw-c1 needs its own var. Read `infrastructure/nas-link-setup/roles/nas-link-route/tasks/main.yml` — the role only references `nas_link_subnet` and `node1_lan_ip` (the gateway), which are already defined and correct. No role changes needed.

- [ ] **Step 2.4: Run the playbook (dry-run first)**

```bash
sudo HOME=/home/kamil-rybacki ansible-playbook \
  infrastructure/nas-link-setup/setup.yml \
  -i infrastructure/nas-link-setup/inventory/hosts.ini \
  --limit compute --check
```
Expected: no errors, "changed" shown for route task

- [ ] **Step 2.5: Apply**

```bash
sudo HOME=/home/kamil-rybacki ansible-playbook \
  infrastructure/nas-link-setup/setup.yml \
  -i infrastructure/nas-link-setup/inventory/hosts.ini \
  --limit compute
```

- [ ] **Step 2.6: Also re-run NAS play to update firewall**

```bash
sudo HOME=/home/kamil-rybacki ansible-playbook \
  infrastructure/nas-link-setup/setup.yml \
  -i infrastructure/nas-link-setup/inventory/hosts.ini \
  --limit nas
```

- [ ] **Step 2.7: Verify lw-c1 can reach lw-nas**

```bash
ssh kamil@192.168.0.107 "ping -c 2 10.0.1.2"
```
Expected: 2 packets transmitted, 0% loss

- [ ] **Step 2.8: Verify lw-c1 can reach Redis and Postgres ports**

```bash
ssh kamil@192.168.0.107 "nc -zv 10.0.1.2 6379 && nc -zv 10.0.1.2 5432"
```
Expected: both connections succeed

- [ ] **Step 2.9: Commit**

```bash
git add infrastructure/nas-link-setup/
git commit -m "feat(nas-link): add lw-c1 route and DB firewall allowlist"
```

---

## Task 3: K3s installation role

**Goal:** Write and test the `k3s` role that installs K3s as a systemd service on a remote Ubuntu host.

**Files:**
- Create: `k8s/k3s-setup/roles/k3s/tasks/main.yml`
- Create: `k8s/k3s-setup/roles/k3s/defaults/main.yml`
- Create: `k8s/k3s-setup/roles/k3s/meta/main.yml`
- Create: `k8s/k3s-setup/roles/k3s/molecule/default/molecule.yml`
- Create: `k8s/k3s-setup/roles/k3s/molecule/default/converge.yml`
- Create: `k8s/k3s-setup/roles/k3s/molecule/default/tests/test_k3s.py`

- [ ] **Step 3.1: Write molecule test (RED)**

```python
# k8s/k3s-setup/roles/k3s/molecule/default/tests/test_k3s.py
def test_k3s_service_running(host):
    svc = host.service("k3s")
    assert svc.is_enabled
    assert svc.is_running

def test_kubectl_available(host):
    result = host.run("kubectl version --client")
    assert result.rc == 0

def test_node_ready(host):
    result = host.run("kubectl get nodes --no-headers")
    assert result.rc == 0
    assert "Ready" in result.stdout

def test_k3s_config_exists(host):
    assert host.file("/etc/rancher/k3s/k3s.yaml").exists
```

- [ ] **Step 3.2: Write molecule config**

```yaml
# k8s/k3s-setup/roles/k3s/molecule/default/molecule.yml
---
dependency:
  name: galaxy
driver:
  name: docker
platforms:
  - name: k3s-test
    image: geerlingguy/docker-ubuntu2404-ansible:latest
    privileged: true
    cgroupns_mode: host
    volumes:
      - /sys/fs/cgroup:/sys/fs/cgroup:rw
    command: /lib/systemd/systemd
    pre_build_image: true
provisioner:
  name: ansible
verifier:
  name: testinfra
```

```yaml
# k8s/k3s-setup/roles/k3s/molecule/default/converge.yml
---
- name: Converge
  hosts: all
  become: true
  roles:
    - role: k3s
```

- [ ] **Step 3.3: Run molecule test to confirm failure**

```bash
cd k8s/k3s-setup
molecule test -s default
```
Expected: FAIL — role directory is empty

- [ ] **Step 3.4: Write role defaults**

```yaml
# k8s/k3s-setup/roles/k3s/defaults/main.yml
---
k3s_version: "v1.32.3+k3s1"
k3s_install_url: "https://get.k3s.io"
k3s_node_ready_retries: 20
k3s_node_ready_delay: 5
```

- [ ] **Step 3.5: Write role meta**

```yaml
# k8s/k3s-setup/roles/k3s/meta/main.yml
---
galaxy_info:
  role_name: k3s
  author: kamil-rybacki
  description: Install K3s on Ubuntu
  min_ansible_version: "2.14"
dependencies: []
```

- [ ] **Step 3.6: Write role tasks**

```yaml
# k8s/k3s-setup/roles/k3s/tasks/main.yml
---
- name: Install K3s
  ansible.builtin.shell: |
    curl -sfL {{ k3s_install_url }} | INSTALL_K3S_VERSION={{ k3s_version }} sh -s - \
      --write-kubeconfig-mode 644
  args:
    creates: /usr/local/bin/k3s
  environment:
    HOME: /root

- name: Enable and start K3s service
  ansible.builtin.systemd:
    name: k3s
    state: started
    enabled: true
    daemon_reload: true

- name: Wait for K3s node to be ready
  ansible.builtin.command: >
    kubectl get nodes --no-headers
  register: _k3s_nodes
  until: "'Ready' in _k3s_nodes.stdout"
  retries: "{{ k3s_node_ready_retries }}"
  delay: "{{ k3s_node_ready_delay }}"
  changed_when: false
  environment:
    KUBECONFIG: /etc/rancher/k3s/k3s.yaml
```

- [ ] **Step 3.7: Run molecule test to confirm pass**

```bash
cd k8s/k3s-setup
molecule test -s default
```
Expected: PASS

- [ ] **Step 3.8: Commit**

```bash
git add k8s/k3s-setup/roles/k3s/
git commit -m "feat(k3s): add k3s installation role with molecule tests"
```

---

## Task 4: Kubeconfig fetch role

**Goal:** Fetch kubeconfig from lw-c1, rewrite server address from 127.0.0.1 to 192.168.0.107, save locally.

**Files:**
- Create: `k8s/k3s-setup/roles/kubeconfig/tasks/main.yml`
- Create: `k8s/k3s-setup/roles/kubeconfig/defaults/main.yml`

- [ ] **Step 4.1: Write defaults**

```yaml
# k8s/k3s-setup/roles/kubeconfig/defaults/main.yml
---
k3s_node_ip: "192.168.0.107"
kubeconfig_remote_path: "/etc/rancher/k3s/k3s.yaml"
kubeconfig_local_path: "{{ lookup('env', 'HOME') }}/.kube/lw-c1.yaml"
```

- [ ] **Step 4.2: Write tasks**

```yaml
# k8s/k3s-setup/roles/kubeconfig/tasks/main.yml
---
- name: Fetch kubeconfig from lw-c1
  ansible.builtin.fetch:
    src: "{{ kubeconfig_remote_path }}"
    dest: "/tmp/lw-c1-kubeconfig.yaml"
    flat: true

- name: Rewrite server address to node LAN IP
  ansible.builtin.replace:
    path: "/tmp/lw-c1-kubeconfig.yaml"
    regexp: 'https://127\.0\.0\.1:6443'
    replace: "https://{{ k3s_node_ip }}:6443"
  delegate_to: localhost
  become: false

- name: Ensure ~/.kube directory exists
  ansible.builtin.file:
    path: "{{ kubeconfig_local_path | dirname }}"
    state: directory
    mode: "0700"
  delegate_to: localhost
  become: false

- name: Install kubeconfig locally
  ansible.builtin.copy:
    src: "/tmp/lw-c1-kubeconfig.yaml"
    dest: "{{ kubeconfig_local_path }}"
    mode: "0600"
  delegate_to: localhost
  become: false

- name: Remove temp kubeconfig
  ansible.builtin.file:
    path: "/tmp/lw-c1-kubeconfig.yaml"
    state: absent
  delegate_to: localhost
  become: false

- name: Verify kubectl can reach lw-c1
  ansible.builtin.command: kubectl get nodes --no-headers
  environment:
    KUBECONFIG: "{{ kubeconfig_local_path }}"
  delegate_to: localhost
  become: false
  register: _kube_nodes
  changed_when: false
  failed_when: "'Ready' not in _kube_nodes.stdout"
```

- [ ] **Step 4.3: Commit**

```bash
git add k8s/k3s-setup/roles/kubeconfig/
git commit -m "feat(k3s): add kubeconfig fetch role"
```

---

## Task 5: K3s full setup playbook

**Goal:** Wire K3s installation, kubeconfig fetch, and management stack into one playbook.

**Files:**
- Create: `k8s/k3s-setup/setup.yml`
- Create: `k8s/k3s-setup/inventory/hosts.ini`
- Create: `k8s/k3s-setup/group_vars/all.yml`
- Create: `k8s/k3s-setup/ansible.cfg`

- [ ] **Step 5.1: Write inventory**

```ini
# k8s/k3s-setup/inventory/hosts.ini
[compute]
lw-c1 ansible_host=192.168.0.107 ansible_user=kamil ansible_python_interpreter=/usr/bin/python3
```

- [ ] **Step 5.2: Write `ansible.cfg`**

```ini
# k8s/k3s-setup/ansible.cfg
[defaults]
roles_path = roles:../helm-setup/roles:../k9s-setup/roles:../headlamp-setup/roles:../argocd-setup/roles
```

- [ ] **Step 5.3: Write `group_vars/all.yml`**

```yaml
# k8s/k3s-setup/group_vars/all.yml
---
# K3s
k3s_version: "v1.32.3+k3s1"
k3s_node_ip: "192.168.0.107"
kubeconfig_local_path: "{{ lookup('env', 'HOME') }}/.kube/lw-c1.yaml"

# Helm
helm_version: "v3.16.4"

# k9s
k9s_version: "v0.32.7"

# Headlamp
headlamp_namespace: headlamp
headlamp_chart_version: "0.25.0"
headlamp_port: 4466
headlamp_service_type: NodePort
headlamp_health_check_retries: 15
headlamp_health_check_delay: 5

# ArgoCD
argocd_namespace: argocd
argocd_version: "v2.13.3"
argocd_port: 8443
argocd_health_check_retries: 20
argocd_health_check_delay: 10
```

- [ ] **Step 5.4: Write `setup.yml`**

```yaml
# k8s/k3s-setup/setup.yml
---
# =============================================================================
# K3s Full Stack Setup — lw-c1
# =============================================================================
# Installs K3s on lw-c1, fetches kubeconfig, and deploys Helm, k9s,
# Headlamp dashboard, and ArgoCD GitOps controller.
#
# Usage:
#   ansible-playbook k8s/k3s-setup/setup.yml \
#     -i k8s/k3s-setup/inventory/hosts.ini \
#     --ask-become-pass
# =============================================================================

- name: Install K3s on lw-c1
  hosts: compute
  become: true
  roles:
    - k3s

- name: Fetch kubeconfig to control node
  hosts: compute
  become: true
  roles:
    - kubeconfig

- name: Install CLI tools on lw-c1
  hosts: compute
  become: true
  roles:
    - helm
    - k9s

- name: Deploy Headlamp dashboard
  hosts: localhost
  connection: local
  environment:
    KUBECONFIG: "{{ kubeconfig_local_path }}"
  roles:
    - headlamp

- name: Deploy ArgoCD GitOps controller
  hosts: localhost
  connection: local
  environment:
    KUBECONFIG: "{{ kubeconfig_local_path }}"
  roles:
    - argocd
```

- [ ] **Step 5.5: Run the playbook**

```bash
sudo HOME=/home/kamil-rybacki ansible-playbook \
  k8s/k3s-setup/setup.yml \
  -i k8s/k3s-setup/inventory/hosts.ini \
  --ask-become-pass
```
Expected: all plays complete, ArgoCD admin password printed at end.

- [ ] **Step 5.6: Verify cluster is healthy**

```bash
KUBECONFIG=~/.kube/lw-c1.yaml kubectl get nodes
KUBECONFIG=~/.kube/lw-c1.yaml kubectl get pods -A
```
Expected: node `lw-c1` in `Ready` state; ArgoCD and Headlamp pods running.

- [ ] **Step 5.7: Commit**

```bash
git add k8s/k3s-setup/
git commit -m "feat(k3s): add K3s full stack setup playbook for lw-c1"
```

---

## Task 6: n8n workers on K3s

**Goal:** Deploy n8n queue-mode workers as a K8s Deployment on lw-c1.

**Pre-condition:** Confirm n8n Postgres password matches Vault.
```bash
# Read n8n DB password from Vault
vault kv get -field=db_password secret/homelab/n8n
# Connect to shared-postgres on lw-nas and verify
ssh kamil@10.0.1.2 "docker exec shared-postgres psql -U n8n -c '\conninfo'"
# If auth fails, sync the password:
ssh kamil@10.0.1.2 "docker exec shared-postgres psql -U postgres \
  -c \"ALTER USER n8n WITH PASSWORD '<vault-password>';\""
```

**Files:**
- Create: `k8s/n8n-workers-setup/setup.yml`
- Create: `k8s/n8n-workers-setup/inventory/localhost.ini`
- Create: `k8s/n8n-workers-setup/group_vars/all.yml`
- Create: `k8s/n8n-workers-setup/roles/n8n-worker/tasks/main.yml`
- Create: `k8s/n8n-workers-setup/roles/n8n-worker/defaults/main.yml`
- Create: `k8s/n8n-workers-setup/roles/n8n-worker/templates/deployment.yml.j2`
- Create: `k8s/n8n-workers-setup/roles/n8n-worker/templates/secret.yml.j2`

- [ ] **Step 6.1: Write `group_vars/all.yml`**

```yaml
# k8s/n8n-workers-setup/group_vars/all.yml
---
kubeconfig_local_path: "{{ lookup('env', 'HOME') }}/.kube/lw-c1.yaml"

# Must match the n8n version running on lw-s1
# Read the current version: ssh kamil@192.168.0.108 "docker inspect n8n | jq -r '.[].Config.Image'"
n8n_version: "latest"   # replace with pinned tag from above command

n8n_worker_namespace: n8n
n8n_worker_replicas: 2
n8n_worker_image: "docker.n8n.io/n8nio/n8n"

# Redis (lw-nas)
n8n_redis_host: "10.0.1.2"
n8n_redis_port: "6379"
n8n_redis_db: "0"

# Postgres (lw-nas) — credentials come from Vault at deploy time
n8n_db_host: "10.0.1.2"
n8n_db_port: "5432"
n8n_db_name: "n8n"
n8n_db_user: "n8n"
```

- [ ] **Step 6.2: Write Secret template**

```yaml
# k8s/n8n-workers-setup/roles/n8n-worker/templates/secret.yml.j2
---
apiVersion: v1
kind: Secret
metadata:
  name: n8n-worker-secrets
  namespace: {{ n8n_worker_namespace }}
type: Opaque
stringData:
  DB_POSTGRESDB_PASSWORD: "{{ _vault_secrets.db_password }}"
```

- [ ] **Step 6.3: Write Deployment template**

```yaml
# k8s/n8n-workers-setup/roles/n8n-worker/templates/deployment.yml.j2
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: n8n-workers
  namespace: {{ n8n_worker_namespace }}
spec:
  replicas: {{ n8n_worker_replicas }}
  selector:
    matchLabels:
      app: n8n-worker
  template:
    metadata:
      labels:
        app: n8n-worker
    spec:
      containers:
        - name: n8n-worker
          image: {{ n8n_worker_image }}:{{ n8n_version }}
          command: ["n8n", "worker"]
          env:
            - name: EXECUTIONS_MODE
              value: "queue"
            - name: QUEUE_BULL_REDIS_HOST
              value: "{{ n8n_redis_host }}"
            - name: QUEUE_BULL_REDIS_PORT
              value: "{{ n8n_redis_port }}"
            - name: QUEUE_BULL_REDIS_DB
              value: "{{ n8n_redis_db }}"
            - name: DB_TYPE
              value: "postgresdb"
            - name: DB_POSTGRESDB_HOST
              value: "{{ n8n_db_host }}"
            - name: DB_POSTGRESDB_PORT
              value: "{{ n8n_db_port }}"
            - name: DB_POSTGRESDB_DATABASE
              value: "{{ n8n_db_name }}"
            - name: DB_POSTGRESDB_USER
              value: "{{ n8n_db_user }}"
            - name: DB_POSTGRESDB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: n8n-worker-secrets
                  key: DB_POSTGRESDB_PASSWORD
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "2Gi"
              cpu: "1000m"
```

- [ ] **Step 6.4: Write role tasks**

```yaml
# k8s/n8n-workers-setup/roles/n8n-worker/tasks/main.yml
---
- name: Create n8n namespace
  ansible.builtin.command: kubectl create namespace {{ n8n_worker_namespace }}
  register: _ns
  changed_when: _ns.rc == 0
  failed_when: _ns.rc != 0 and 'already exists' not in _ns.stderr
  environment:
    KUBECONFIG: "{{ kubeconfig_local_path }}"

- name: Apply n8n worker Secret
  ansible.builtin.template:
    src: secret.yml.j2
    dest: /tmp/n8n-worker-secret.yml
    mode: "0600"
  no_log: true

- name: Apply Secret to cluster
  ansible.builtin.command: kubectl apply -f /tmp/n8n-worker-secret.yml
  environment:
    KUBECONFIG: "{{ kubeconfig_local_path }}"
  no_log: true

- name: Remove temp secret file
  ansible.builtin.file:
    path: /tmp/n8n-worker-secret.yml
    state: absent

- name: Apply n8n worker Deployment
  ansible.builtin.template:
    src: deployment.yml.j2
    dest: /tmp/n8n-worker-deployment.yml
    mode: "0644"

- name: Apply Deployment to cluster
  ansible.builtin.command: kubectl apply -f /tmp/n8n-worker-deployment.yml
  environment:
    KUBECONFIG: "{{ kubeconfig_local_path }}"

- name: Remove temp deployment file
  ansible.builtin.file:
    path: /tmp/n8n-worker-deployment.yml
    state: absent

- name: Wait for n8n workers to be ready
  ansible.builtin.command: >
    kubectl rollout status deployment/n8n-workers
    -n {{ n8n_worker_namespace }} --timeout=120s
  environment:
    KUBECONFIG: "{{ kubeconfig_local_path }}"
  changed_when: false
```

- [ ] **Step 6.5: Write role defaults and setup.yml**

```yaml
# k8s/n8n-workers-setup/roles/n8n-worker/defaults/main.yml
---
n8n_worker_namespace: n8n
n8n_worker_replicas: 2
```

```yaml
# k8s/n8n-workers-setup/setup.yml
---
# =============================================================================
# n8n Workers Setup — lw-c1 K3s
# =============================================================================
# Reads n8n DB password from Vault, deploys n8n queue workers to K3s.
#
# Pre-condition: K3s running on lw-c1, kubeconfig at ~/.kube/lw-c1.yaml
# Pre-condition: n8n Postgres password synced (see spec Task 6 pre-condition)
#
# Usage:
#   ansible-playbook k8s/n8n-workers-setup/setup.yml \
#     -i k8s/n8n-workers-setup/inventory/localhost.ini
# =============================================================================

- name: Load secrets from Vault
  hosts: localhost
  connection: local
  gather_facts: true
  tasks:
    - name: Check Vault availability
      ansible.builtin.include_tasks: "{{ playbook_dir }}/../../common/vault-integration/check.yml"
    - name: Load secrets from Vault
      ansible.builtin.include_tasks: "{{ playbook_dir }}/../../common/vault-integration/load.yml"
      vars:
        vault_service_name: "n8n"
      when: _vault_available | bool

- name: Deploy n8n workers to K3s
  hosts: localhost
  connection: local
  roles:
    - n8n-worker
```

```ini
# k8s/n8n-workers-setup/inventory/localhost.ini
[local]
localhost ansible_connection=local ansible_python_interpreter=/usr/bin/python3
```

- [ ] **Step 6.6: Pin n8n version to match lw-s1**

```bash
ssh kamil@192.168.0.108 "docker inspect n8n | python3 -c \"import sys,json; print(json.load(sys.stdin)[0]['Config']['Image'])\""
```
Copy the tag and update `n8n_version` in `k8s/n8n-workers-setup/group_vars/all.yml`.

- [ ] **Step 6.7: Run the playbook**

```bash
sudo HOME=/home/kamil-rybacki ansible-playbook \
  k8s/n8n-workers-setup/setup.yml \
  -i k8s/n8n-workers-setup/inventory/localhost.ini
```
Expected: Deployment created, workers rollout complete.

- [ ] **Step 6.8: Verify workers are running**

```bash
KUBECONFIG=~/.kube/lw-c1.yaml kubectl get pods -n n8n
```
Expected: 2 pods in `Running` state.

```bash
KUBECONFIG=~/.kube/lw-c1.yaml kubectl logs -n n8n -l app=n8n-worker --tail=20
```
Expected: logs showing worker polling queue — no auth errors.

- [ ] **Step 6.9: Commit**

```bash
git add k8s/n8n-workers-setup/
git commit -m "feat(n8n): add n8n worker Deployment on lw-c1 K3s"
```

---

## Task 7: GitHub Actions runners on K3s

**Pre-condition:** You have a GitHub PAT with `repo` scope stored in Vault:
```bash
vault kv patch secret/homelab/github runner_pat=<your-pat>
```

**Files:**
- Create: `k8s/github-runners-setup/setup.yml`
- Create: `k8s/github-runners-setup/inventory/localhost.ini`
- Create: `k8s/github-runners-setup/group_vars/all.yml`
- Create: `k8s/github-runners-setup/roles/github-runner/tasks/main.yml`
- Create: `k8s/github-runners-setup/roles/github-runner/defaults/main.yml`
- Create: `k8s/github-runners-setup/roles/github-runner/templates/deployment.yml.j2`
- Create: `k8s/github-runners-setup/roles/github-runner/templates/secret.yml.j2`

- [ ] **Step 7.1: Write `group_vars/all.yml`**

```yaml
# k8s/github-runners-setup/group_vars/all.yml
---
kubeconfig_local_path: "{{ lookup('env', 'HOME') }}/.kube/lw-c1.yaml"

runner_namespace: github-runners
runner_replicas: 2
runner_image: "myoung34/github-runner:latest"
runner_repo_url: "https://github.com/kamilandrzejrybacki-inc/n8n-workflows"
runner_name_prefix: "lw-c1"
runner_labels: "lw-c1,k8s,compute"
```

- [ ] **Step 7.2: Write Secret template**

```yaml
# k8s/github-runners-setup/roles/github-runner/templates/secret.yml.j2
---
apiVersion: v1
kind: Secret
metadata:
  name: github-runner-secrets
  namespace: {{ runner_namespace }}
type: Opaque
stringData:
  GITHUB_TOKEN: "{{ _vault_secrets.runner_pat }}"
```

- [ ] **Step 7.3: Write Deployment template**

```yaml
# k8s/github-runners-setup/roles/github-runner/templates/deployment.yml.j2
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: github-runner
  namespace: {{ runner_namespace }}
spec:
  replicas: {{ runner_replicas }}
  selector:
    matchLabels:
      app: github-runner
  template:
    metadata:
      labels:
        app: github-runner
    spec:
      containers:
        - name: github-runner
          image: {{ runner_image }}
          env:
            - name: RUNNER_NAME_PREFIX
              value: "{{ runner_name_prefix }}"
            - name: RUNNER_WORKDIR
              value: "/tmp/runner"
            - name: REPO_URL
              value: "{{ runner_repo_url }}"
            - name: LABELS
              value: "{{ runner_labels }}"
            - name: ACCESS_TOKEN
              valueFrom:
                secretKeyRef:
                  name: github-runner-secrets
                  key: GITHUB_TOKEN
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "2Gi"
              cpu: "1000m"
```

- [ ] **Step 7.4: Write role tasks**

```yaml
# k8s/github-runners-setup/roles/github-runner/tasks/main.yml
---
- name: Create github-runners namespace
  ansible.builtin.command: kubectl create namespace {{ runner_namespace }}
  register: _ns
  changed_when: _ns.rc == 0
  failed_when: _ns.rc != 0 and 'already exists' not in _ns.stderr
  environment:
    KUBECONFIG: "{{ kubeconfig_local_path }}"

- name: Apply runner Secret
  ansible.builtin.template:
    src: secret.yml.j2
    dest: /tmp/runner-secret.yml
    mode: "0600"
  no_log: true

- name: Apply Secret to cluster
  ansible.builtin.command: kubectl apply -f /tmp/runner-secret.yml
  environment:
    KUBECONFIG: "{{ kubeconfig_local_path }}"
  no_log: true

- name: Remove temp secret file
  ansible.builtin.file:
    path: /tmp/runner-secret.yml
    state: absent

- name: Apply runner Deployment
  ansible.builtin.template:
    src: deployment.yml.j2
    dest: /tmp/runner-deployment.yml
    mode: "0644"

- name: Apply Deployment to cluster
  ansible.builtin.command: kubectl apply -f /tmp/runner-deployment.yml
  environment:
    KUBECONFIG: "{{ kubeconfig_local_path }}"

- name: Remove temp deployment file
  ansible.builtin.file:
    path: /tmp/runner-deployment.yml
    state: absent

- name: Wait for runners to be ready
  ansible.builtin.command: >
    kubectl rollout status deployment/github-runner
    -n {{ runner_namespace }} --timeout=120s
  environment:
    KUBECONFIG: "{{ kubeconfig_local_path }}"
  changed_when: false
```

- [ ] **Step 7.5: Write role defaults and setup.yml**

```yaml
# k8s/github-runners-setup/roles/github-runner/defaults/main.yml
---
runner_namespace: github-runners
runner_replicas: 2
```

```yaml
# k8s/github-runners-setup/setup.yml
---
# =============================================================================
# GitHub Actions Runners Setup — lw-c1 K3s
# =============================================================================
# Usage:
#   ansible-playbook k8s/github-runners-setup/setup.yml \
#     -i k8s/github-runners-setup/inventory/localhost.ini
# =============================================================================

- name: Load runner PAT from Vault
  hosts: localhost
  connection: local
  gather_facts: true
  tasks:
    - name: Check Vault availability
      ansible.builtin.include_tasks: "{{ playbook_dir }}/../../common/vault-integration/check.yml"
    - name: Load secrets from Vault
      ansible.builtin.include_tasks: "{{ playbook_dir }}/../../common/vault-integration/load.yml"
      vars:
        vault_service_name: "github"
      when: _vault_available | bool

- name: Deploy GitHub runners to K3s
  hosts: localhost
  connection: local
  roles:
    - github-runner
```

```ini
# k8s/github-runners-setup/inventory/localhost.ini
[local]
localhost ansible_connection=local ansible_python_interpreter=/usr/bin/python3
```

- [ ] **Step 7.6: Run the playbook**

```bash
sudo HOME=/home/kamil-rybacki ansible-playbook \
  k8s/github-runners-setup/setup.yml \
  -i k8s/github-runners-setup/inventory/localhost.ini
```

- [ ] **Step 7.7: Verify runners registered on GitHub**

Check: `https://github.com/kamilandrzejrybacki-inc/n8n-workflows/settings/actions/runners`
Expected: 2 runners named `lw-c1-*` in `Idle` state.

- [ ] **Step 7.8: Commit**

```bash
git add k8s/github-runners-setup/
git commit -m "feat(runners): add GitHub Actions runner Deployment on lw-c1 K3s"
```

---

## Task 8: vCluster test environment

**Files:**
- Create: `k8s/vcluster-setup/setup.yml`
- Create: `k8s/vcluster-setup/inventory/localhost.ini`
- Create: `k8s/vcluster-setup/group_vars/all.yml`
- Create: `k8s/vcluster-setup/roles/vcluster/tasks/main.yml`
- Create: `k8s/vcluster-setup/roles/vcluster/defaults/main.yml`

- [ ] **Step 8.1: Write `group_vars/all.yml`**

```yaml
# k8s/vcluster-setup/group_vars/all.yml
---
kubeconfig_local_path: "{{ lookup('env', 'HOME') }}/.kube/lw-c1.yaml"
vcluster_namespace: "test"
vcluster_name: "test-cluster"
vcluster_chart_version: "0.20.0"
vcluster_k3s_image: "rancher/k3s:v1.30.2-k3s1"
vcluster_ready_retries: 20
vcluster_ready_delay: 10
```

- [ ] **Step 8.2: Write role defaults**

```yaml
# k8s/vcluster-setup/roles/vcluster/defaults/main.yml
---
vcluster_namespace: "test"
vcluster_name: "test-cluster"
vcluster_chart_version: "0.20.0"
vcluster_ready_retries: 20
vcluster_ready_delay: 10
```

- [ ] **Step 8.3: Write role tasks**

```yaml
# k8s/vcluster-setup/roles/vcluster/tasks/main.yml
---
- name: Add vCluster Helm repo
  ansible.builtin.command: helm repo add loft-sh https://charts.loft.sh
  environment:
    KUBECONFIG: "{{ kubeconfig_local_path }}"
  changed_when: false

- name: Update Helm repos
  ansible.builtin.command: helm repo update
  environment:
    KUBECONFIG: "{{ kubeconfig_local_path }}"
  changed_when: false

- name: Create test namespace
  ansible.builtin.command: kubectl create namespace {{ vcluster_namespace }}
  register: _ns
  changed_when: _ns.rc == 0
  failed_when: _ns.rc != 0 and 'already exists' not in _ns.stderr
  environment:
    KUBECONFIG: "{{ kubeconfig_local_path }}"

- name: Install vCluster
  ansible.builtin.command: >
    helm upgrade --install {{ vcluster_name }}
    loft-sh/vcluster
    --version {{ vcluster_chart_version }}
    --namespace {{ vcluster_namespace }}
    --set controlPlane.distro.k3s.enabled=true
    --wait --timeout=300s
  environment:
    KUBECONFIG: "{{ kubeconfig_local_path }}"

- name: Display vCluster access instructions
  ansible.builtin.debug:
    msg: |
      vCluster '{{ vcluster_name }}' deployed in namespace '{{ vcluster_namespace }}'.

      To connect:
        vcluster connect {{ vcluster_name }} -n {{ vcluster_namespace }}

      This opens a proxy kubeconfig for the virtual cluster.
      Run tests against it, then disconnect:
        vcluster disconnect
```

- [ ] **Step 8.4: Write setup.yml**

```yaml
# k8s/vcluster-setup/setup.yml
---
# =============================================================================
# vCluster Setup — test environment on lw-c1 K3s
# =============================================================================
# Usage:
#   ansible-playbook k8s/vcluster-setup/setup.yml \
#     -i k8s/vcluster-setup/inventory/localhost.ini
# =============================================================================

- name: Deploy vCluster test environment
  hosts: localhost
  connection: local
  roles:
    - vcluster
```

```ini
# k8s/vcluster-setup/inventory/localhost.ini
[local]
localhost ansible_connection=local ansible_python_interpreter=/usr/bin/python3
```

- [ ] **Step 8.5: Run the playbook**

```bash
sudo HOME=/home/kamil-rybacki ansible-playbook \
  k8s/vcluster-setup/setup.yml \
  -i k8s/vcluster-setup/inventory/localhost.ini
```

- [ ] **Step 8.6: Verify vCluster is running**

```bash
KUBECONFIG=~/.kube/lw-c1.yaml kubectl get pods -n test
```
Expected: vCluster pods in `Running` state.

- [ ] **Step 8.7: Commit**

```bash
git add k8s/vcluster-setup/
git commit -m "feat(vcluster): add vCluster test environment on lw-c1 K3s"
```

---

## Task 9: Enable n8n queue mode on lw-s1

**Goal:** Switch n8n on lw-s1 from single-process to queue mode. Workers on lw-c1 are already running — this task activates queue dispatch.

**Files:**
- Modify: `automation/n8n-setup/group_vars/all.yml`
- Modify: `automation/n8n-setup/roles/n8n/tasks/main.yml`

- [ ] **Step 9.1: Add queue mode vars to `group_vars/all.yml`**

Append to `automation/n8n-setup/group_vars/all.yml`:
```yaml
# Queue mode — set to true to switch n8n to queue execution mode
n8n_queue_mode: false

# Redis queue (lw-nas) — only used when n8n_queue_mode is true
n8n_queue_redis_host: "10.0.1.2"
n8n_queue_redis_port: "6379"
n8n_queue_redis_db: "0"
```

- [ ] **Step 9.2: Add queue mode env vars to n8n container task**

Read `automation/n8n-setup/roles/n8n/tasks/main.yml`. In the `Start n8n container` task, extend `_n8n_env` to conditionally include queue vars. Find the vars block under the task and add:

```yaml
    _n8n_queue_env: >-
      {{
        {
          'EXECUTIONS_MODE': 'queue',
          'QUEUE_BULL_REDIS_HOST': n8n_queue_redis_host,
          'QUEUE_BULL_REDIS_PORT': n8n_queue_redis_port,
          'QUEUE_BULL_REDIS_DB': n8n_queue_redis_db
        }
        if n8n_queue_mode | bool else {}
      }}
```

And update the `env` line on the container task:
```yaml
    env: "{{ _n8n_env | combine(_n8n_public_url_env) | combine(_n8n_queue_env) }}"
```

Keep `comparisons.env: ignore` unchanged — the shim recreates the container via Docker API directly and Ansible must not fight it. Queue-mode vars will be written on the next container creation triggered by the shim.

- [ ] **Step 9.3: Confirm no shim changes needed**

The vault-shim's `_build_env` function preserves all env vars that do NOT start with `N8N_VAR_` or equal `N8N_BLOCK_ENV_ACCESS_IN_NODE`. Queue-mode vars (`EXECUTIONS_MODE`, `QUEUE_BULL_REDIS_*`) have no such prefix and are therefore already preserved on container recreation. No changes to the shim are needed.

- [ ] **Step 9.4: Enable queue mode in `group_vars/all.yml`**

Update the value just set:
```yaml
n8n_queue_mode: true
```

- [ ] **Step 9.5: Run n8n playbook targeting lw-s1**

```bash
sudo HOME=/home/kamil-rybacki ansible-playbook \
  automation/n8n-setup/setup.yml \
  -i automation/n8n-setup/inventory/hosts.ini \
  --ask-become-pass
```
When prompted for host IP, enter `192.168.0.108`. Ansible will recreate the n8n container with queue mode env vars.

- [ ] **Step 9.6: Verify queue mode is active**

```bash
ssh kamil@192.168.0.108 "docker exec n8n printenv EXECUTIONS_MODE"
```
Expected: `queue`

- [ ] **Step 9.7: Trigger a test workflow execution and verify worker picks it up**

In the n8n UI, run any simple workflow manually. Then check worker logs:
```bash
KUBECONFIG=~/.kube/lw-c1.yaml kubectl logs -n n8n -l app=n8n-worker --tail=30 -f
```
Expected: log line showing the worker picking up and completing the execution.

- [ ] **Step 9.8: Commit**

```bash
git add automation/n8n-setup/
git commit -m "feat(n8n): enable queue mode on lw-s1, workers run on lw-c1"
```

---

## Task 10: Remove GitHub runner from lw-s1

**Goal:** Remove the old runner from lw-s1 only after lw-c1 runners are confirmed active.

**Pre-condition:** lw-c1 runners are visible and idle at `https://github.com/kamilandrzejrybacki-inc/n8n-workflows/settings/actions/runners`

- [ ] **Step 10.1: Trigger a GitHub Actions workflow and verify it runs on lw-c1**

Push a no-op commit to the n8n-workflows repo and confirm the job is picked up by a `lw-c1-*` runner (visible in the Actions tab).

- [ ] **Step 10.2: Remove the github-runner container from lw-s1**

Read `automation/n8n-setup/setup.yml` and the n8n-vault-shim role to locate where the GitHub runner is defined (it may be in a separate role or docker-compose). Remove the container definition and re-run the playbook, or stop + remove it manually:

```bash
ssh kamil@192.168.0.108 "docker stop github-runner && docker rm github-runner"
```

- [ ] **Step 10.3: Remove the runner from GitHub settings**

In `https://github.com/kamilandrzejrybacki-inc/n8n-workflows/settings/actions/runners`, remove the offline lw-s1 runner entry.

- [ ] **Step 10.4: Update lw-s1 architecture memory**

Update `/home/kamil-rybacki/.claude/projects/-home-kamil-rybacki-Code-ansible/memory/project_homelab_node2.md` — remove the `github-runner` container row.

Update `project_homelab_architecture.md` — move `GitHub Actions runner` from `lw-s1` to `lw-c1` in the service map.

Update `project_homelab_node1.md` equivalent for lw-c1 — create `project_homelab_node_c1.md` (new memory file) documenting lw-c1's services.

- [ ] **Step 10.5: Final verification**

```bash
# All K3s workloads healthy
KUBECONFIG=~/.kube/lw-c1.yaml kubectl get pods -A

# n8n queue mode confirmed
ssh kamil@192.168.0.108 "docker exec n8n printenv EXECUTIONS_MODE"

# NAS reachable from lw-c1
ssh kamil@192.168.0.107 "nc -zv 10.0.1.2 6379 && nc -zv 10.0.1.2 5432"
```

- [ ] **Step 10.6: Final commit**

```bash
git add .
git commit -m "chore(lw-c1): complete compute node migration - remove lw-s1 GitHub runner"
```

---

## Runbook: Updating worker secrets after Vault rotation

When Vault secrets for n8n are rotated:
```bash
sudo HOME=/home/kamil-rybacki ansible-playbook \
  k8s/n8n-workers-setup/setup.yml \
  -i k8s/n8n-workers-setup/inventory/localhost.ini
```
This re-reads from Vault and updates the K8s Secret. Workers restart automatically on Secret change.

## Runbook: Recreating vCluster for a clean test run

```bash
KUBECONFIG=~/.kube/lw-c1.yaml helm uninstall test-cluster -n test
sudo HOME=/home/kamil-rybacki ansible-playbook \
  k8s/vcluster-setup/setup.yml \
  -i k8s/vcluster-setup/inventory/localhost.ini
```
