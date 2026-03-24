---
name: docker-compose-jinja2-empty-sections
description: "Wrap Docker Compose section keywords in conditionals to prevent empty depends_on/volumes validation failures"
user-invocable: false
origin: auto-extracted
---

# Docker Compose Jinja2 Empty Section Validation

**Extracted:** 2026-03-23
**Context:** Ansible roles using Jinja2 templated Docker Compose files with conditional services

## Problem
When Jinja2 conditionals remove all items from `depends_on:`, `volumes:`, or `networks:` sections, Docker Compose validation fails:
- `services.X.depends_on must be a array`
- `volumes must be a mapping`

## Solution
Wrap the entire section keyword in a conditional, not just the items:

BAD — leaves empty `depends_on:` when both conditions are true:
```yaml
    depends_on:
{% if not use_shared_db %}
      - postgres
{% endif %}
{% if not use_shared_redis %}
      - redis
{% endif %}
```

GOOD — omits `depends_on:` entirely when all deps are shared:
```yaml
{% if not (use_shared_db and use_shared_redis) %}
    depends_on:
{% if not use_shared_db %}
      - postgres
{% endif %}
{% if not use_shared_redis %}
      - redis
{% endif %}
{% endif %}
```

Same pattern applies to `volumes:` (must be a mapping, not empty).

## When to Use
When writing Jinja2 templates for Docker Compose files where services, volumes, or dependencies are conditionally included/excluded.
