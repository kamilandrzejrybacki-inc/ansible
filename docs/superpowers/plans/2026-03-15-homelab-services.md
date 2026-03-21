# Homelab Services Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Pi-hole (integrated into secure-homelab-access), Uptime Kuma, Vaultwarden, and Paperless-ngx playbooks.

**Architecture:** Pi-hole is a new role in the existing `security/secure-homelab-access` stack (Caddy + Authelia + WireGuard DNS integration). The other 3 are standalone playbooks under `home-services/` following the two-play pattern (localhost prompt → remote deploy via `add_host`).

**Tech Stack:** Ansible 2.10+, community.docker collection, Docker containers

**Spec:** `docs/superpowers/specs/2026-03-15-homelab-services-design.md`

---

## Chunk 1: Pi-hole Integration

### Task 1: Add Pi-hole group_vars and role skeleton

**Files:**
- Modify: `security/secure-homelab-access/group_vars/all.yml`
- Create: `security/secure-homelab-access/roles/pihole/meta/main.yml`
- Create: `security/secure-homelab-access/roles/pihole/defaults/main.yml`
- Create: `security/secure-homelab-access/roles/pihole/handlers/main.yml`
- Create: `security/secure-homelab-access/roles/pihole/tasks/main.yml`

- [ ] **Step 1: Add Pi-hole vars to group_vars/all.yml**

Append before the `# -- Subdomain Prefixes` section:

```yaml
# -- Pi-hole (DNS) -----------------------------------------------------------
pihole_container_name: "pihole"
pihole_image: "pihole/pihole:2024.07.0"
pihole_data_dir: "{{ docker_data_dir }}/pihole"
pihole_web_port: 8053
pihole_dns_ip: "172.20.0.10"
pihole_health_check_retries: 12
pihole_health_check_delay: 5
```

Also add to the Subdomain Prefixes section:

```yaml
subdomain_pihole: "pihole"
```

Also change wireguard_dns:

```yaml
# FROM:
wireguard_dns: "1.1.1.1,1.0.0.1"
# TO:
wireguard_dns: "{{ pihole_dns_ip }}"
```

- [ ] **Step 2: Create roles/pihole/meta/main.yml**

```yaml
---
galaxy_info:
  role_name: pihole
  author: kamilrybacki
  description: Deploy Pi-hole DNS sinkhole in Docker
  min_ansible_version: "2.10"
dependencies:
  - docker
```

- [ ] **Step 3: Create roles/pihole/defaults/main.yml**

```yaml
---
pihole_upstream_dns: "1.1.1.1;1.0.0.1"
```

- [ ] **Step 4: Create roles/pihole/handlers/main.yml**

```yaml
---
- name: Restart systemd-resolved
  ansible.builtin.systemd:
    name: systemd-resolved
    state: restarted
```

- [ ] **Step 5: Create roles/pihole/tasks/main.yml**

```yaml
---
- name: Disable systemd-resolved stub listener
  ansible.builtin.lineinfile:
    path: /etc/systemd/resolved.conf
    regexp: "^#?DNSStubListener="
    line: "DNSStubListener=no"
    backup: true
  notify: Restart systemd-resolved

- name: Flush handlers to apply resolved changes
  ansible.builtin.meta: flush_handlers

- name: Symlink resolv.conf to systemd-resolved
  ansible.builtin.file:
    src: /run/systemd/resolve/resolv.conf
    dest: /etc/resolv.conf
    state: link
    force: true

- name: Create Pi-hole data directories
  ansible.builtin.file:
    path: "{{ item }}"
    state: directory
    mode: "0755"
  loop:
    - "{{ pihole_data_dir }}/etc-pihole"
    - "{{ pihole_data_dir }}/etc-dnsmasq.d"

- name: Deploy Pi-hole container
  community.docker.docker_container:
    name: "{{ pihole_container_name }}"
    image: "{{ pihole_image }}"
    state: started
    restart_policy: unless-stopped
    env:
      WEBPASSWORD: "{{ pihole_password }}"
      PIHOLE_DNS_: "{{ pihole_upstream_dns }}"
      DNSMASQ_LISTENING: "all"
    volumes:
      - "{{ pihole_data_dir }}/etc-pihole:/etc/pihole"
      - "{{ pihole_data_dir }}/etc-dnsmasq.d:/etc/dnsmasq.d"
    ports:
      - "53:53/tcp"
      - "53:53/udp"
    networks:
      - name: "{{ docker_network_name }}"
        ipv4_address: "{{ pihole_dns_ip }}"
  no_log: true

- name: Wait for Pi-hole to become reachable
  ansible.builtin.uri:
    url: "http://localhost:{{ pihole_web_port }}/admin/"
    status_code: [200, 302]
  register: pihole_health
  until: pihole_health is not failed
  retries: "{{ pihole_health_check_retries }}"
  delay: "{{ pihole_health_check_delay }}"
```

- [ ] **Step 6: Commit**

```bash
git add security/secure-homelab-access/group_vars/all.yml \
      security/secure-homelab-access/roles/pihole/
git commit -m "feat(secure-homelab-access): add pihole role and group_vars"
```

### Task 2: Integrate Pi-hole into setup.yml, Caddy, and Homepage

**Files:**
- Modify: `security/secure-homelab-access/setup.yml`
- Modify: `security/secure-homelab-access/roles/caddy/templates/Caddyfile.j2`
- Modify: `security/secure-homelab-access/roles/homepage/templates/services.yaml.j2`

- [ ] **Step 1: Update setup.yml — renumber prompts [1/8]→[1/9] through [8/8]→[8/9], add [9/9] Pi-hole password prompt**

Add to `vars_prompt` after the Authelia email prompt:

```yaml
    # -- Pi-hole --
    - name: prompt_pihole_password
      prompt: "[9/9] Pi-hole admin password (for DNS dashboard)"
      private: true
      confirm: true
```

Update all existing prompt labels from `/8]` to `/9]`.

- [ ] **Step 2: Update setup.yml — add pihole_password to set_fact pre_task**

In the "Set prompted values as facts" task, add:

```yaml
        pihole_password: "{{ prompt_pihole_password }}"
```

- [ ] **Step 3: Update setup.yml — add firewall rules for DNS**

In the "Update firewall ports" task, add port 53 to both TCP and UDP:

```yaml
        firewall_allowed_tcp_ports:
          - "{{ ssh_port }}"
          - "53"
        firewall_allowed_udp_ports:
          - "{{ wireguard_port }}"
          - "53"
```

- [ ] **Step 4: Update setup.yml — insert pihole role after docker, before wireguard**

```yaml
    - role: docker
      tags: [docker]

    - role: pihole
      tags: [pihole, dns]

    - role: wireguard
      tags: [wireguard, vpn]
```

- [ ] **Step 5: Update setup.yml — add Pi-hole to deployment summary and post_tasks**

In the deployment summary debug message, add:

```
              {{ subdomain_pihole }}.{{ domain }}     → Pi-hole DNS dashboard
```

In the post_tasks "Deployment Complete" message, add:

```
             https://{{ subdomain_pihole }}.{{ domain }} → DNS ad-blocking dashboard
```

- [ ] **Step 6: Add Pi-hole to Caddyfile.j2**

Append before the closing of the file:

```
# Pi-hole DNS dashboard
{{ subdomain_pihole }}.{{ domain }} {
	import authelia
	reverse_proxy {{ pihole_container_name }}:{{ pihole_web_port }}
}
```

- [ ] **Step 7: Add Pi-hole to Homepage services.yaml.j2**

Add to the Infrastructure section:

```yaml
    - Pi-hole:
        icon: pi-hole.png
        href: "https://{{ subdomain_pihole }}.{{ domain }}"
        description: "DNS ad-blocking & local DNS"
```

- [ ] **Step 8: Commit**

```bash
git add security/secure-homelab-access/setup.yml \
      security/secure-homelab-access/roles/caddy/templates/Caddyfile.j2 \
      security/secure-homelab-access/roles/homepage/templates/services.yaml.j2
git commit -m "feat(secure-homelab-access): integrate pihole with caddy, homepage, and wireguard DNS"
```

---

## Chunk 2: Uptime Kuma Playbook

### Task 3: Create kuma-setup playbook

**Files:**
- Create: `monitoring/kuma-setup/inventory/hosts.ini`
- Create: `monitoring/kuma-setup/group_vars/all.yml`
- Create: `monitoring/kuma-setup/roles/docker/defaults/main.yml`
- Create: `monitoring/kuma-setup/roles/docker/meta/main.yml`
- Create: `monitoring/kuma-setup/roles/docker/tasks/main.yml`
- Create: `monitoring/kuma-setup/roles/kuma/defaults/main.yml`
- Create: `monitoring/kuma-setup/roles/kuma/meta/main.yml`
- Create: `monitoring/kuma-setup/roles/kuma/tasks/main.yml`
- Create: `monitoring/kuma-setup/setup.yml`

- [ ] **Step 1: Create inventory/hosts.ini**

```ini
[local]
localhost ansible_connection=local ansible_python_interpreter=/usr/bin/python3
```

- [ ] **Step 2: Create group_vars/all.yml**

```yaml
---
kuma_container_name: kuma
kuma_image: "louislam/uptime-kuma:1.23.16"
kuma_port: 3001
kuma_volume_name: kuma_data
kuma_restart_policy: unless-stopped
kuma_health_check_retries: 12
kuma_health_check_delay: 5
```

- [ ] **Step 3: Create docker role**

Copy the docker role from `automation/n8n-setup/roles/docker/` (defaults, meta, tasks — identical pattern).

- [ ] **Step 4: Create roles/kuma/meta/main.yml**

```yaml
---
galaxy_info:
  role_name: kuma
  author: kamilrybacki
  description: Deploy Uptime Kuma monitoring in Docker
  min_ansible_version: "2.10"
dependencies:
  - docker
```

- [ ] **Step 5: Create roles/kuma/defaults/main.yml**

```yaml
---
# Defaults are in group_vars/all.yml
```

- [ ] **Step 6: Create roles/kuma/tasks/main.yml**

```yaml
---
- name: Install Python Docker SDK
  ansible.builtin.apt:
    name: python3-docker
    state: present

- name: Create Docker volume for Uptime Kuma data
  community.docker.docker_volume:
    name: "{{ kuma_volume_name }}"
    state: present

- name: Start Uptime Kuma container
  community.docker.docker_container:
    name: "{{ kuma_container_name }}"
    image: "{{ kuma_image }}"
    state: started
    restart_policy: "{{ kuma_restart_policy }}"
    published_ports:
      - "127.0.0.1:{{ kuma_port }}:3001"
    volumes:
      - "{{ kuma_volume_name }}:/app/data"

- name: Wait for Uptime Kuma to become reachable
  ansible.builtin.uri:
    url: "http://localhost:{{ kuma_port }}"
    status_code: [200, 302]
  register: kuma_health
  until: kuma_health is not failed
  retries: "{{ kuma_health_check_retries }}"
  delay: "{{ kuma_health_check_delay }}"

- name: Display Uptime Kuma access information
  ansible.builtin.debug:
    msg: |
      Uptime Kuma is running at http://{{ inventory_hostname }}:{{ kuma_port }}

      Next steps:
        1. Open the URL above in your browser.
        2. Create your admin account on first launch.
        3. Add monitors for your services.

      To put behind a reverse proxy, configure your proxy to forward
      to 127.0.0.1:{{ kuma_port }}.
```

- [ ] **Step 7: Create setup.yml**

```yaml
---
# =============================================================================
# Uptime Kuma Setup
# =============================================================================
# Deploys Uptime Kuma monitoring on a remote host via Docker.
#
# Usage:
#   ansible-playbook monitoring/kuma-setup/setup.yml \
#     -i monitoring/kuma-setup/inventory/hosts.ini \
#     --ask-become-pass
# =============================================================================

- name: Gather host details
  hosts: localhost
  connection: local
  gather_facts: false
  vars_prompt:
    - name: target_host_ip
      prompt: |

        ══════════════════════════════════════════════
          Uptime Kuma Setup Wizard
        ══════════════════════════════════════════════

        [1/2] IP or hostname of the target machine
      private: false

    - name: target_ssh_user
      prompt: "[2/2] SSH user for the target machine"
      private: false

  tasks:
    - name: Add target host to dynamic inventory
      ansible.builtin.add_host:
        name: "{{ target_host_ip }}"
        groups: kuma_hosts
        ansible_user: "{{ target_ssh_user }}"
        ansible_python_interpreter: /usr/bin/python3

- name: Install Docker and deploy Uptime Kuma
  hosts: kuma_hosts
  become: true
  roles:
    - docker
    - kuma
```

- [ ] **Step 8: Commit**

```bash
git add monitoring/kuma-setup/
git commit -m "feat: add kuma-setup playbook for Uptime Kuma monitoring"
```

---

## Chunk 3: Vaultwarden Playbook

### Task 4: Create vaultwarden-setup playbook

**Files:**
- Create: `security/vaultwarden-setup/inventory/hosts.ini`
- Create: `security/vaultwarden-setup/group_vars/all.yml`
- Create: `security/vaultwarden-setup/roles/docker/defaults/main.yml`
- Create: `security/vaultwarden-setup/roles/docker/meta/main.yml`
- Create: `security/vaultwarden-setup/roles/docker/tasks/main.yml`
- Create: `security/vaultwarden-setup/roles/vaultwarden/defaults/main.yml`
- Create: `security/vaultwarden-setup/roles/vaultwarden/meta/main.yml`
- Create: `security/vaultwarden-setup/roles/vaultwarden/tasks/main.yml`
- Create: `security/vaultwarden-setup/setup.yml`

- [ ] **Step 1: Create inventory/hosts.ini**

```ini
[local]
localhost ansible_connection=local ansible_python_interpreter=/usr/bin/python3
```

- [ ] **Step 2: Create group_vars/all.yml**

```yaml
---
vaultwarden_container_name: vaultwarden
vaultwarden_image: "vaultwarden/server:1.32.7"
vaultwarden_port: 8080
vaultwarden_data_dir: /opt/vaultwarden
vaultwarden_restart_policy: unless-stopped
vaultwarden_health_check_retries: 12
vaultwarden_health_check_delay: 5
```

- [ ] **Step 3: Create docker role**

Copy the docker role from `automation/n8n-setup/roles/docker/` (identical pattern).

- [ ] **Step 4: Create roles/vaultwarden/meta/main.yml**

```yaml
---
galaxy_info:
  role_name: vaultwarden
  author: kamilrybacki
  description: Deploy Vaultwarden password manager in Docker
  min_ansible_version: "2.10"
dependencies:
  - docker
```

- [ ] **Step 5: Create roles/vaultwarden/defaults/main.yml**

```yaml
---
# Defaults are in group_vars/all.yml
```

- [ ] **Step 6: Create roles/vaultwarden/tasks/main.yml**

```yaml
---
- name: Install Python Docker SDK
  ansible.builtin.apt:
    name: python3-docker
    state: present

- name: Create Vaultwarden data directory
  ansible.builtin.file:
    path: "{{ vaultwarden_data_dir }}"
    state: directory
    mode: "0700"
    owner: root
    group: root

- name: Hash admin token with argon2id via Vaultwarden CLI
  ansible.builtin.command: >-
    docker run --rm {{ vaultwarden_image }}
    /vaultwarden hash --preset owasp
  args:
    stdin: "{{ vaultwarden_admin_token }}"
  register: _vw_hash_result
  changed_when: false
  no_log: true

- name: Set hashed admin token fact
  ansible.builtin.set_fact:
    _vw_hashed_token: "{{ _vw_hash_result.stdout | trim }}"
  no_log: true

- name: Start Vaultwarden container
  community.docker.docker_container:
    name: "{{ vaultwarden_container_name }}"
    image: "{{ vaultwarden_image }}"
    state: started
    restart_policy: "{{ vaultwarden_restart_policy }}"
    env:
      SIGNUPS_ALLOWED: "false"
      ADMIN_TOKEN: "{{ _vw_hashed_token }}"
      ROCKET_PORT: "80"
    published_ports:
      - "127.0.0.1:{{ vaultwarden_port }}:80"
    volumes:
      - "{{ vaultwarden_data_dir }}:/data"
  no_log: true

- name: Wait for Vaultwarden to become reachable
  ansible.builtin.uri:
    url: "http://localhost:{{ vaultwarden_port }}"
    status_code: [200, 302]
  register: vw_health
  until: vw_health is not failed
  retries: "{{ vaultwarden_health_check_retries }}"
  delay: "{{ vaultwarden_health_check_delay }}"

- name: Display Vaultwarden access information
  ansible.builtin.debug:
    msg: |
      Vaultwarden is running at http://{{ inventory_hostname }}:{{ vaultwarden_port }}

      Admin panel: http://{{ inventory_hostname }}:{{ vaultwarden_port }}/admin
      Public registration is disabled. Create accounts via the admin panel.

      To put behind a reverse proxy, configure your proxy to forward
      to 127.0.0.1:{{ vaultwarden_port }}.
```

- [ ] **Step 7: Create setup.yml**

```yaml
---
# =============================================================================
# Vaultwarden Setup
# =============================================================================
# Deploys Vaultwarden (self-hosted Bitwarden) on a remote host via Docker.
#
# Usage:
#   ansible-playbook security/vaultwarden-setup/setup.yml \
#     -i security/vaultwarden-setup/inventory/hosts.ini \
#     --ask-become-pass
# =============================================================================

- name: Gather host details
  hosts: localhost
  connection: local
  gather_facts: false
  vars_prompt:
    - name: target_host_ip
      prompt: |

        ══════════════════════════════════════════════
          Vaultwarden Setup Wizard
        ══════════════════════════════════════════════

        [1/3] IP or hostname of the target machine
      private: false

    - name: target_ssh_user
      prompt: "[2/3] SSH user for the target machine"
      private: false

    - name: vaultwarden_admin_token
      prompt: "[3/3] Admin token for the /admin panel"
      private: true
      confirm: true

  tasks:
    - name: Add target host to dynamic inventory
      ansible.builtin.add_host:
        name: "{{ target_host_ip }}"
        groups: vaultwarden_hosts
        ansible_user: "{{ target_ssh_user }}"
        ansible_python_interpreter: /usr/bin/python3
        vaultwarden_admin_token: "{{ vaultwarden_admin_token }}"
      no_log: true

- name: Install Docker and deploy Vaultwarden
  hosts: vaultwarden_hosts
  become: true
  roles:
    - docker
    - vaultwarden
```

- [ ] **Step 8: Commit**

```bash
git add security/vaultwarden-setup/
git commit -m "feat: add vaultwarden-setup playbook for self-hosted password manager"
```

---

## Chunk 4: Paperless-ngx Playbook

### Task 5: Create paperless-setup playbook

**Files:**
- Create: `files/paperless-setup/inventory/hosts.ini`
- Create: `files/paperless-setup/group_vars/all.yml`
- Create: `files/paperless-setup/roles/docker/defaults/main.yml`
- Create: `files/paperless-setup/roles/docker/meta/main.yml`
- Create: `files/paperless-setup/roles/docker/tasks/main.yml`
- Create: `files/paperless-setup/roles/paperless/defaults/main.yml`
- Create: `files/paperless-setup/roles/paperless/meta/main.yml`
- Create: `files/paperless-setup/roles/paperless/tasks/main.yml`
- Create: `files/paperless-setup/roles/paperless/templates/docker-compose.yml.j2`
- Create: `files/paperless-setup/setup.yml`

- [ ] **Step 1: Create inventory/hosts.ini**

```ini
[local]
localhost ansible_connection=local ansible_python_interpreter=/usr/bin/python3
```

- [ ] **Step 2: Create group_vars/all.yml**

```yaml
---
paperless_container_name: paperless
paperless_image: "ghcr.io/paperless-ngx/paperless-ngx:2.14.7"
paperless_port: 8000
paperless_data_dir: /opt/paperless
paperless_document_path: ""
paperless_redis_image: "redis:7.4"
paperless_postgres_image: "postgres:16.6"
paperless_restart_policy: unless-stopped
paperless_health_check_retries: 20
paperless_health_check_delay: 10
```

- [ ] **Step 3: Create docker role**

Copy the docker role from `automation/n8n-setup/roles/docker/` (identical pattern).

- [ ] **Step 4: Create roles/paperless/meta/main.yml**

```yaml
---
galaxy_info:
  role_name: paperless
  author: kamilrybacki
  description: Deploy Paperless-ngx document management via Docker Compose
  min_ansible_version: "2.10"
dependencies:
  - docker
```

- [ ] **Step 5: Create roles/paperless/defaults/main.yml**

```yaml
---
# Defaults are in group_vars/all.yml
```

- [ ] **Step 6: Create roles/paperless/templates/docker-compose.yml.j2**

```yaml
services:
  redis:
    container_name: {{ paperless_container_name }}-redis
    image: {{ paperless_redis_image }}
    restart: {{ paperless_restart_policy }}
    volumes:
      - paperless-redis-data:/data
    networks:
      - paperless-net

  db:
    container_name: {{ paperless_container_name }}-db
    image: {{ paperless_postgres_image }}
    restart: {{ paperless_restart_policy }}
    environment:
      POSTGRES_DB: paperless
      POSTGRES_USER: paperless
      POSTGRES_PASSWORD: "{{ paperless_db_password }}"
    volumes:
      - paperless-db-data:/var/lib/postgresql/data
    networks:
      - paperless-net

  webserver:
    container_name: {{ paperless_container_name }}
    image: {{ paperless_image }}
    restart: {{ paperless_restart_policy }}
    depends_on:
      - db
      - redis
    ports:
      - "127.0.0.1:{{ paperless_port }}:8000"
    volumes:
      - paperless-data:/usr/src/paperless/data
{% if paperless_document_path | length > 0 %}
      - {{ paperless_document_path }}:/usr/src/paperless/media
{% else %}
      - paperless-media:/usr/src/paperless/media
{% endif %}
    environment:
      PAPERLESS_REDIS: "redis://redis:6379"
      PAPERLESS_DBHOST: db
      PAPERLESS_DBPASS: "{{ paperless_db_password }}"
      PAPERLESS_SECRET_KEY: "{{ paperless_secret_key }}"
      PAPERLESS_ADMIN_USER: "{{ paperless_admin_user }}"
      PAPERLESS_ADMIN_PASSWORD: "{{ paperless_admin_password }}"
    networks:
      - paperless-net

volumes:
  paperless-redis-data:
  paperless-db-data:
  paperless-data:
{% if paperless_document_path | length == 0 %}
  paperless-media:
{% endif %}

networks:
  paperless-net:
    driver: bridge
```

- [ ] **Step 7: Create roles/paperless/tasks/main.yml**

```yaml
---
- name: Install Python Docker SDK
  ansible.builtin.apt:
    name: python3-docker
    state: present

- name: Create Paperless data directory
  ansible.builtin.file:
    path: "{{ paperless_data_dir }}"
    state: directory
    mode: "0700"
    owner: root
    group: root

- name: Create document storage directory (if custom path)
  ansible.builtin.file:
    path: "{{ paperless_document_path }}"
    state: directory
    mode: "0755"
  when: paperless_document_path | length > 0

- name: Auto-generate secrets
  ansible.builtin.set_fact:
    paperless_db_password: "{{ lookup('password', '/dev/null chars=ascii_letters,digits length=64') }}"
    paperless_secret_key: "{{ lookup('password', '/dev/null chars=ascii_letters,digits length=64') }}"
  no_log: true

- name: Template Docker Compose file
  ansible.builtin.template:
    src: docker-compose.yml.j2
    dest: "{{ paperless_data_dir }}/docker-compose.yml"
    mode: "0600"
    owner: root
    group: root
  no_log: true

- name: Deploy Paperless-ngx stack
  community.docker.docker_compose_v2:
    project_src: "{{ paperless_data_dir }}"
    state: present

- name: Wait for Paperless-ngx to become reachable
  ansible.builtin.uri:
    url: "http://localhost:{{ paperless_port }}"
    status_code: [200, 302]
  register: paperless_health
  until: paperless_health is not failed
  retries: "{{ paperless_health_check_retries }}"
  delay: "{{ paperless_health_check_delay }}"

- name: Display Paperless-ngx access information
  ansible.builtin.debug:
    msg: |
      Paperless-ngx is running at http://{{ inventory_hostname }}:{{ paperless_port }}

      Admin user: {{ paperless_admin_user }}
      Document storage: {{ paperless_document_path | default('Docker volume (paperless-media)', true) }}

      To put behind a reverse proxy, configure your proxy to forward
      to 127.0.0.1:{{ paperless_port }}.
```

- [ ] **Step 8: Create setup.yml**

```yaml
---
# =============================================================================
# Paperless-ngx Setup
# =============================================================================
# Deploys Paperless-ngx document management on a remote host via Docker Compose.
#
# Usage:
#   ansible-playbook files/paperless-setup/setup.yml \
#     -i files/paperless-setup/inventory/hosts.ini \
#     --ask-become-pass
# =============================================================================

- name: Gather host details
  hosts: localhost
  connection: local
  gather_facts: false
  vars_prompt:
    - name: target_host_ip
      prompt: |

        ══════════════════════════════════════════════
          Paperless-ngx Setup Wizard
        ══════════════════════════════════════════════

        [1/5] IP or hostname of the target machine
      private: false

    - name: target_ssh_user
      prompt: "[2/5] SSH user for the target machine"
      private: false

    - name: paperless_admin_user
      prompt: "[3/5] Admin username"
      default: "admin"
      private: false

    - name: paperless_admin_password
      prompt: "[4/5] Admin password"
      private: true
      confirm: true

    - name: paperless_document_path
      prompt: "[5/5] Document storage path (leave blank for Docker volume, or enter NAS/external path)"
      default: ""
      private: false

  tasks:
    - name: Add target host to dynamic inventory
      ansible.builtin.add_host:
        name: "{{ target_host_ip }}"
        groups: paperless_hosts
        ansible_user: "{{ target_ssh_user }}"
        ansible_python_interpreter: /usr/bin/python3
        paperless_admin_user: "{{ paperless_admin_user }}"
        paperless_admin_password: "{{ paperless_admin_password }}"
        paperless_document_path: "{{ paperless_document_path }}"
      no_log: true

- name: Install Docker and deploy Paperless-ngx
  hosts: paperless_hosts
  become: true
  roles:
    - docker
    - paperless
```

- [ ] **Step 9: Commit**

```bash
git add files/paperless-setup/
git commit -m "feat: add paperless-setup playbook for document management"
```

---

## Chunk 5: README Update and Final Push

### Task 6: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add new entries to README**

In the `home-services/` table, add:

```markdown
| [`monitoring/kuma-setup/`](./monitoring/kuma-setup/) | Uptime Kuma monitoring — Docker, health checks, status pages |
| [`security/vaultwarden-setup/`](./security/vaultwarden-setup/) | Vaultwarden password manager — Docker, admin-only registration |
| [`files/paperless-setup/`](./files/paperless-setup/) | Paperless-ngx document management — Docker Compose, Redis, PostgreSQL |
```

In the `infrastructure/` table description for `secure-homelab-access`, update to mention Pi-hole:

```markdown
| [`security/secure-homelab-access/`](./security/secure-homelab-access/) | Secure homelab remote access — WireGuard, Authelia, Caddy, Pi-hole, fail2ban, Cockpit |
```

- [ ] **Step 2: Commit and push**

```bash
git add README.md
git commit -m "docs: add kuma, vaultwarden, paperless, and pihole to README"
git push origin main
```
