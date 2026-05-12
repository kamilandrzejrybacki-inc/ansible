# tplink-dhcp

CLI helper for managing DHCP address reservations on a TP-Link
TL-WR740N (or compatible) running stock firmware. The router exposes
no API — this scrapes the web UI over HTTP.

## Setup

```bash
chmod +x dev-tools/tplink-dhcp/tplink-dhcp.sh

cat > ~/.tplink-admin <<'EOF'
ROUTER_HOST=192.168.0.1
ROUTER_USER=admin
ROUTER_PASS=<your admin password>
EOF
chmod 600 ~/.tplink-admin
```

## Usage

```bash
# List reservations
dev-tools/tplink-dhcp/tplink-dhcp.sh list

# Reserve an IP for a MAC (overwrites existing reservation for that MAC)
dev-tools/tplink-dhcp/tplink-dhcp.sh add 30:16:9D:D5:6E:93 192.168.0.115
dev-tools/tplink-dhcp/tplink-dhcp.sh add D8:CB:8A:5F:93:EA 192.168.0.111

# Remove
dev-tools/tplink-dhcp/tplink-dhcp.sh remove 30:16:9D:D5:6E:93
```

## Caveats

- HTTP only — admin password crosses the LAN in plaintext on every call.
- Form field names assume firmware 3.16+. Newer firmwares may differ;
  inspect the live HTML if `add` silently no-ops.
- `~/.tplink-admin` is **never** committed (matched by `.env*` /
  custom gitignore rules) — keep it out of version control.
