# bambulab-setup

Ansible playbook to integrate a BambuLab X1C 3D printer with an existing Home Assistant instance. Installs the ha-bambulab community integration, deploys a Lovelace dashboard with printer status, live camera, and AMS filament tracking, and optionally configures webhook alerts for print events.

## What it does

1. **Installs ha-bambulab** — downloads the latest release into HA's `custom_components/bambu_lab/`
2. **Deploys a Lovelace dashboard** — printer status, print progress, temperatures, live camera, AMS filament tracking (type, color, humidity, remaining %)
3. **Configures print event alerts** (optional) — webhook notifications for print completed, print failed, and filament runout

## Prerequisites

- Home Assistant running and accessible (deployed via `homeassistant-setup` playbook)
- HACS activated in the HA UI (see [homeassistant-setup README](../homeassistant-setup/README.md))

## Usage

```bash
# Install required collection (if not already installed)
ansible-galaxy collection install community.docker

# Run the playbook
ansible-playbook bambulab-setup/setup.yml \
  -i bambulab-setup/inventory/hosts.ini \
  --ask-become-pass
```

The playbook will prompt for:

| Prompt | Description | Default |
|---|---|---|
| Home Assistant host IP | Target machine running HA | — |
| SSH user | SSH user on the HA host | — |
| HA port | Home Assistant web port | 8123 |
| Webhook URL | Alert destination — Discord/Slack/n8n (optional, leave blank to skip) | "" |
| Printer name | Entity ID prefix matching your printer (e.g. `x1c`) | x1c |

## Post-install manual steps

After the playbook completes:

1. **Add the BambuLab integration in HA UI:**
   Settings → Devices & Services → + Add Integration → search "Bambu Lab" → Cloud → enter your BambuLab account email and password → select **Global** region → choose your printer from the list

2. **Enable LAN Mode Liveview on the printer** (for camera feed):
   Printer touchscreen → Settings → Network → enable "LAN Mode Liveview"
   This does **not** disable the Handy app or BambuLab Cloud connectivity.

3. **Dashboard populates automatically** after step 1 — navigate to the BambuLab X1C dashboard in the HA sidebar.

## Entity ID convention

All entities use the printer name as a prefix, matching ha-bambulab's default naming:

```
sensor.<printer_name>_print_status
sensor.<printer_name>_print_progress
sensor.<printer_name>_nozzle_temperature
sensor.<printer_name>_bed_temperature
sensor.<printer_name>_chamber_temperature
sensor.<printer_name>_current_layer
sensor.<printer_name>_total_layer_count
sensor.<printer_name>_remaining_time
sensor.<printer_name>_tray_1_type       (AMS slots 1–4)
sensor.<printer_name>_tray_1_color
sensor.<printer_name>_tray_1_remain
sensor.<printer_name>_humidity_index
camera.<printer_name>_camera
```

The default printer name is `x1c`. If your printer shows up in HA with a different prefix, update the `printer_name` prompt accordingly.

## AMS slots

The dashboard and filament runout alerts are generated for `ams_slots` (default: 4 for the X1C AMS). Adjust this in `group_vars/all.yml` for other configurations:

| Configuration | `ams_slots` |
|---|---|
| X1C with AMS (4-slot) | 4 |
| X1C with AMS Lite (2-slot) | 2 |
| X1C without AMS | 0 |

## Roles

| Role | Description |
|---|---|
| `bambulab` | Download and install ha-bambulab integration into custom_components |
| `dashboard` | Deploy Lovelace dashboard with printer status, camera, and AMS tracking |
| `alerts` | Create webhook automations for print events (optional) |

## Structure

```
bambulab-setup/
├── setup.yml
├── README.md
├── group_vars/
│   └── all.yml
├── inventory/
│   └── hosts.ini
└── roles/
    ├── bambulab/
    │   ├── tasks/main.yml
    │   ├── defaults/main.yml
    │   └── meta/main.yml
    ├── dashboard/
    │   ├── tasks/main.yml
    │   ├── templates/lovelace.yaml.j2
    │   └── meta/main.yml
    └── alerts/
        ├── tasks/main.yml
        ├── templates/automations.yaml.j2
        └── meta/main.yml
```
