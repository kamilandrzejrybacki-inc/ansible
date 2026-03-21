---

# NAS Setup Playbook

Ansible playbook to set up a NAS on a Dell Optiplex (or any Linux box) using **mergerfs + SnapRAID** for redundant storage with NFS sharing.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Dell Optiplex                         │
│                                                         │
│  USB Hub ──┬── /dev/sdb ──► data disk1 ──┐              │
│            ├── /dev/sdc ──► data disk2 ──┼─► mergerfs   │
│            ├── /dev/sdd ──► data disk3 ──┘   /mnt/pool  │
│            └── /dev/sde ──► parity ──► SnapRAID         │
│                                                         │
│  Internal ─── /dev/sda ──► /mnt/storage (2TB, no RAID)  │
│                                                         │
│  NFS Server ──► exports /mnt/pool + /mnt/storage        │
└─────────────────────────────────────────────────────────┘
```

## Features

- **mergerfs**: Pools data drives into a single mount point
- **SnapRAID**: Scheduled parity sync (nightly) and scrub (weekly)
- **NFS**: Exports pool and internal storage over the network
- **smartmontools**: Drive health monitoring with email alerts
- **rsync backups**: Nightly backup from pool to internal drive

## Configurable Redundancy

Edit `group_vars/all.yml` to adjust the number of drives and redundancy ratio:

```yaml
# 4 drives, 1 parity (3+1, RAID5-like)
all_usb_drives:
  - /dev/sdb
  - /dev/sdc
  - /dev/sdd
  - /dev/sde
parity_drive_count: 1

# 6 drives, 2 parity (4+2, RAID6-like)
all_usb_drives:
  - /dev/sdb
  - /dev/sdc
  - /dev/sdd
  - /dev/sde
  - /dev/sdf
  - /dev/sdg
parity_drive_count: 2
```

The playbook automatically splits drives into data and parity groups.

## Usage

```bash
# Dry run first
ansible-playbook -i inventory/localhost.ini nas.yml --check

# Run the playbook
ansible-playbook -i inventory/localhost.ini nas.yml
```

## Before Running

1. Update drive paths in `group_vars/all.yml` to match your system (`lsblk`)
2. Set `smartd_alert_email` to your email address
3. Set `nfs_allowed_network` to your LAN subnet
4. Set `parity_drive_count` for your desired redundancy level

## Cron Schedule (default)

| Job             | Schedule              |
|-----------------|-----------------------|
| SnapRAID sync   | 3:00 AM daily         |
| SnapRAID scrub  | 5:00 AM every Sunday  |
| rsync backup    | 4:00 AM daily         |
