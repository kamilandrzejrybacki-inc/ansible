---
name: hermes-model-settings-override
description: "Hermes webui persists default_model in settings.json which overrides config.yaml — must update both"
user-invocable: false
origin: auto-extracted
---

# Hermes Model Change Requires settings.json Update

**Extracted:** 2026-04-24
**Context:** Changing Hermes model via Ansible group_vars + playbook

## Problem
`config.yaml` has `model.default` set correctly but Hermes still reports the old model.
`/opt/hermes/data/webui-state/settings.json` persists `default_model` and **takes precedence** over `config.yaml`. Ansible only updates `config.yaml` — it does not touch `settings.json`.

## Solution
After running the playbook, also update `settings.json` on lw-pi:

```bash
ssh kamil@192.168.0.109 "sudo python3 -c \"
import json
p = '/opt/hermes/data/webui-state/settings.json'
s = json.load(open(p))
s['default_model'] = 'gpt-5.5'
json.dump(s, open(p, 'w'), indent=2)
\""
ssh kamil@192.168.0.109 "docker restart hermes-webui"
```

Or add a task to the Ansible playbook that patches `settings.json` directly (e.g. via `ansible.builtin.template` or a `json_patch` task).

## When to Use
Any time `hermes_model` is changed in `group_vars/all.yml` and deployed — verify and patch `settings.json` afterward.
