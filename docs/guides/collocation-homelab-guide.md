# Collocation for Homelab: A Practical Guide

## What Is Collocation?

**Collocation** (often shortened to "colo") is the practice of housing your
personally-owned server hardware in a professional data center facility instead
of running it at home. You ship or deliver your gear to a colocation provider,
they rack it, supply power, cooling, network connectivity, and physical
security — and you retain full control of the hardware and software.

```
 Your Home                          Colocation Facility
┌─────────────────┐                ┌──────────────────────────────┐
│                  │   VPN / SSH    │  ┌────────┐  ┌────────┐     │
│  Laptop / PC  ◄─┼───────────────►│  │ Your   │  │ Your   │     │
│                  │                │  │ Server │  │ Server │     │
│  (management)    │                │  │   #1   │  │   #2   │     │
│                  │                │  └────┬───┘  └────┬───┘     │
└─────────────────┘                │       │            │         │
                                   │  ─────┴────────────┴─────    │
                                   │       Data Center Network    │
                                   │       (1–10 Gbps uplink)     │
                                   └──────────────────────────────┘
```

### Collocation vs. Other Options

| Aspect | Homelab (at home) | Collocation | Cloud VPS (AWS/Hetzner) |
|---|---|---|---|
| **Hardware ownership** | You own it | You own it | Provider owns it |
| **Upfront cost** | Hardware purchase | Hardware purchase + setup fee | None |
| **Monthly cost** | Electricity + internet | Colo fee ($30–$150/U/mo) | Instance fees |
| **Network quality** | Residential ISP | Enterprise-grade, BGP peers | Enterprise-grade |
| **Upload bandwidth** | Typically 10–50 Mbps | 1–10 Gbps symmetric | Varies (egress fees) |
| **Power reliability** | No redundancy | Dual-feed UPS + generator | Managed by provider |
| **Physical access** | Instant | Scheduled or limited | None |
| **Noise / heat** | Your problem | Their problem | N/A |
| **Latitude to tinker** | Unlimited | Full (your hardware) | Limited to VM/container |

## Why Consider Collocation for Your Homelab?

### Problems collocation solves

1. **Bandwidth limitations** — Residential ISPs offer asymmetric connections.
   If you self-host services you access remotely (Seafile, Paperless, Outline),
   your upload speed is the bottleneck. A colo facility typically provides
   1 Gbps symmetric or better.

2. **Power reliability** — Home circuits have no UPS, no generator, no
   redundant feeds. A data center provides N+1 or 2N power with automatic
   failover.

3. **Noise and heat** — A 2U server with 8 fans running at 60% is roughly
   55–65 dB. That's fine in a data center; it's miserable in an apartment.

4. **Electricity cost** — Depending on your region, residential electricity
   can be $0.15–0.40/kWh. Some colo providers include power in the monthly
   fee, or charge at wholesale rates ($0.05–0.10/kWh).

5. **Static IPs and reverse DNS** — Most colo providers assign you a static
   IPv4 address (or a small block) and allow rDNS configuration, which is
   essential for self-hosted mail and other services.

### When collocation does NOT make sense

- Your homelab is a single Raspberry Pi or mini-PC drawing 15W
- You need constant physical access for hardware tinkering
- You're in a region with no nearby colo facilities
- Your use case is purely local (home automation, media on LAN)

## Finding a Collocation Provider

### What to look for

| Feature | Minimum | Ideal |
|---|---|---|
| **Space** | 1U or quarter-rack | Half-rack with room to grow |
| **Bandwidth** | 1 Gbps unmetered | 10 Gbps with burstable |
| **Power** | 1A @ 120V (~120W) | 2A+ @ 208V (~400W+) |
| **IP addresses** | 1 IPv4 + /64 IPv6 | /29 IPv4 + /48 IPv6 |
| **Remote hands** | Available on request | Included (basic tasks free) |
| **Remote access** | SSH / VPN | IPMI / iDRAC / iLO KVM |
| **Contract** | Month-to-month | Month-to-month |
| **SLA** | 99.9% uptime | 99.99% uptime |

### Types of providers

1. **Large carriers** (Equinix, Digital Realty, CoreSite) — Enterprise pricing,
   typically require full or half cabinets. Overkill for homelabs.

2. **Regional / boutique colos** — Smaller facilities that cater to individuals
   and small businesses. Often offer single-U pricing. This is your target.

3. **Community colos** — Some hackerspaces and community networks offer
   shared rack space at cost. Check local maker communities.

> **Tip:** Search for `"colocation 1u" your-city` or check community
> resources like [ServeTheHome forums](https://forums.servethehome.com/)
> and r/homelab for regional recommendations.

## Preparing Your Hardware for Collocation

### Choosing the right server

For colocation, prefer:

- **Rack-mount form factor** (1U–4U) — Tower servers waste space and
  most providers charge per-U
- **IPMI / iDRAC / iLO** — Out-of-band management is critical when you
  can't physically touch the machine
- **Dual PSU** — Take advantage of redundant power feeds
- **Low power draw** — Your power allocation is finite; efficiency matters
- **ECC RAM** — Data integrity for long-running unattended systems

Good candidates:
- Dell PowerEdge R630/R640/R650 (1U)
- HPE ProLiant DL360 Gen9/Gen10 (1U)
- Supermicro 1U/2U chassis with X11/X12 boards

### Pre-deployment checklist

Before shipping or delivering your server:

```
☐  Firmware updated (BIOS, BMC/IPMI, NIC, RAID controller)
☐  IPMI/iDRAC configured with static IP or DHCP
☐  OS installed and accessible via SSH
☐  VPN endpoint configured (WireGuard recommended)
☐  Firewall rules locked down (only VPN + essential ports)
☐  Monitoring agent installed (LibreNMS, Alloy, node_exporter)
☐  Burn-in test completed (stress-ng, memtest86+, fio)
☐  Labeled all cables and ports
☐  Documented MAC addresses for all NICs
☐  Serial number and asset tag recorded
```

## Network Architecture

### Recommended topology

```
┌─────────── Home Network ───────────┐
│                                     │
│  ┌──────────┐     ┌──────────────┐ │
│  │ Workstat. │     │ Home services│ │
│  │ / Laptop  │     │ (HA, media)  │ │
│  └─────┬─────┘    └──────┬───────┘ │
│        │                  │         │
│  ──────┴──────────────────┴──────   │
│            Home LAN                 │
│               │                     │
│        ┌──────┴──────┐              │
│        │  WireGuard  │              │
│        │   Client    │              │
│        └──────┬──────┘              │
└───────────────┼─────────────────────┘
                │
          ══════╪═══════  (Internet)
                │
┌───────────────┼─────────────────────┐
│  Colo    ┌────┴─────┐              │
│          │ WireGuard │              │
│          │  Server   │              │
│          └────┬──────┘              │
│               │                     │
│  ─────────────┴──────────────────   │
│          Colo VLAN / LAN            │
│      ┌────────┴─────────┐          │
│  ┌───┴────┐         ┌───┴────┐     │
│  │ Server │         │ Server │     │
│  │  #1    │         │  #2    │     │
│  └────────┘         └────────┘     │
└─────────────────────────────────────┘
```

### WireGuard site-to-site VPN

A site-to-site WireGuard tunnel between your home and colo is the backbone of
a hybrid setup. This lets you:

- Manage colo servers as if they were on your LAN
- Route traffic between home and colo services
- Keep IPMI/management interfaces off the public internet

Example WireGuard configuration for the colo side:

```ini
# /etc/wireguard/wg-home.conf (on colo server)
[Interface]
Address = 10.10.0.1/24
ListenPort = 51820
PrivateKey = <colo-private-key>

[Peer]
# Home endpoint
PublicKey = <home-public-key>
AllowedIPs = 10.10.0.2/32, 192.168.1.0/24
Endpoint = home.example.com:51820
PersistentKeepalive = 25
```

### DNS considerations

- Use **split-horizon DNS** so `service.lab.example.com` resolves to the
  colo IP externally and the WireGuard IP internally
- Consider running a secondary DNS server at the colo for redundancy
- Tools in this repo: the `secure-homelab` playbook already configures
  Pi-hole/AdGuard and can be adapted for split-DNS

## Leveraging This Ansible Repo for Collocation

This repository's playbooks are designed for remote provisioning — making
them ideal for managing colocated hardware. Here's how to use them:

### Initial provisioning

1. **Prepare inventory** — Add your colo server to a dedicated inventory group:

   ```ini
   # inventory/hosts.ini
   [colo]
   colo-server-1 ansible_host=203.0.113.10 ansible_user=deploy

   [colo:vars]
   ansible_ssh_common_args='-o ProxyJump=none'
   ```

2. **Run the security hardening playbook first**:
   ```bash
   cd security/secure-homelab-setup
   ansible-playbook setup.yml
   ```
   This sets up firewall rules, fail2ban, SSH hardening, and optionally
   WireGuard VPN and Authelia 2FA.

3. **Deploy monitoring**:
   ```bash
   cd monitoring/librenms-setup
   ansible-playbook setup.yml
   ```
   Remote hardware monitoring is non-negotiable for colo. LibreNMS gives
   you SNMP-based hardware health, bandwidth graphs, and alerting.

### Recommended playbook deployment order for colo

| Order | Playbook | Why |
|---|---|---|
| 1 | `security/secure-homelab-setup` | Lock down access before anything else |
| 2 | `security/vault-setup` | Centralized secrets management |
| 3 | `monitoring/librenms-setup` | Hardware + network monitoring |
| 4 | `monitoring/uptime-kuma-setup` | Service uptime checks |
| 5 | `files/seafile-setup` | File sync (benefits from colo bandwidth) |
| 6 | `files/paperless-setup` | Document management |
| 7 | `infrastructure/outline-setup` | Wiki / knowledge base |
| 8 | `ai/dify-setup` | LLM platform (benefits from colo GPU) |

### Hybrid home + colo architecture

The most practical homelab collocation setup is **hybrid** — keep latency-
sensitive and local-only services at home, move bandwidth-heavy and always-on
services to the colo:

```
┌─────────────── At Home ──────────────────┐
│                                           │
│  Home Automation (HA, Zigbee, Z-Wave)     │
│  Media Server (Plex/Jellyfin for LAN)     │
│  3D Printer Monitoring (BambuLab)         │
│  Desktop Environment (i3wm, AudioRelay)   │
│  Local development / testing              │
│                                           │
└───────────────────────────────────────────┘
          │
     WireGuard VPN
          │
┌─────────────── At Colo ──────────────────┐
│                                           │
│  File Sync (Seafile) — fast uploads       │
│  Document Mgmt (Paperless) — always on    │
│  Knowledge Base (Outline) — team access   │
│  Monitoring (LibreNMS) — external view    │
│  AI/LLM (Dify) — GPU + bandwidth         │
│  Uptime Monitoring (Kuma) — external      │
│  Kubernetes Cluster (k8s/) — workloads    │
│  Automation (n8n) — webhooks + APIs       │
│                                           │
└───────────────────────────────────────────┘
```

## Cost Analysis

### Typical monthly costs

| Item | Low end | High end |
|---|---|---|
| 1U colocation | $30/mo | $100/mo |
| Power (if metered) | $10/mo | $50/mo |
| IP addresses (extra) | $2–5/IP | $5–10/IP |
| Remote hands | Free (basic) | $50–100/hr |
| **Total** | **~$40/mo** | **~$160/mo** |

### Break-even comparison

Running a Dell R640 at home (~200W idle):
- 200W × 24h × 30d = 144 kWh/month
- At $0.25/kWh = **$36/month in electricity alone**
- Plus: noise, heat, residential bandwidth limits, no power redundancy

A $50/month colo with included power can be cost-neutral or cheaper while
providing dramatically better connectivity and reliability.

## Operational Practices

### Must-haves for remote hardware

1. **Out-of-band management (IPMI/iDRAC/iLO)** — You cannot walk over to
   press the power button. IPMI provides remote console, power cycling, and
   hardware sensor data.

2. **Monitoring and alerting** — Use LibreNMS (included in this repo) for:
   - CPU/RAM/disk/NIC utilization
   - Hardware sensor data (temps, fan RPM, PSU health)
   - SNMP traps for hardware events
   - Alert routing to email / Slack / PagerDuty

3. **Automated backups** — With no physical access, data loss recovery is
   harder. Use the `borgmatic` role or `restic` to back up to a separate
   location (home NAS, object storage, second colo).

4. **Configuration as code** — This entire repo exists for this reason.
   Every service should be reproducible from Ansible. If hardware fails,
   you should be able to deploy onto replacement hardware with a single
   playbook run.

5. **Serial console / SOL** — Configure Serial-over-LAN as a fallback if
   IPMI web console is unreliable.

### Maintenance windows

- Coordinate with your colo provider for any hardware swaps
- Schedule firmware updates during low-usage periods
- Test IPMI connectivity **before** rebooting for kernel updates
- Keep a spare boot drive pre-configured at home, ready to ship

## Security Considerations

Colocated hardware sits on a network you don't fully control. Additional
precautions beyond the standard `secure-homelab` playbook:

1. **Full-disk encryption** — Use LUKS with remote unlock via `dropbear-initramfs`
   or Tang/Clevis for automated network-bound decryption
2. **Firewall everything** — Default-deny inbound; only allow VPN, IPMI
   (from provider's management VLAN), and essential services
3. **Encrypt IPMI traffic** — Enable HTTPS for the BMC web interface,
   change default credentials, restrict to management VLAN
4. **Physical security** — Ask about cage/cabinet locks, access logging,
   and surveillance at the facility
5. **Tamper evidence** — Consider chassis intrusion detection alerts via IPMI

## Getting Started: Step by Step

1. **Research local colo providers** — Look for boutique/regional providers
   offering per-U pricing with month-to-month contracts
2. **Acquire suitable hardware** — A used 1U server with IPMI (Dell R640,
   HP DL360 Gen10) can be found for $200–500
3. **Prepare the server at home** — Install OS, configure IPMI, set up
   WireGuard, run burn-in tests
4. **Run the security playbook** — `security/secure-homelab-setup`
5. **Deploy to the colo** — Deliver or ship the server
6. **Verify remote access** — Confirm SSH, VPN, and IPMI all work
7. **Deploy services** — Use this repo's playbooks to stand up your stack
8. **Set up monitoring** — LibreNMS + Uptime Kuma for full observability
9. **Migrate services gradually** — Move one service at a time, verify,
   then proceed

## Further Reading

- [ServeTheHome — Colocation guides](https://www.servethehome.com/)
- [r/homelab — Colocation experiences](https://www.reddit.com/r/homelab/)
- [WireGuard documentation](https://www.wireguard.com/)
- This repo's `security/secure-homelab-setup/README.md` for baseline hardening
