# Deployment: https://2048coach.com

| | |
|---|---|
| Server | netcup VPS 500 G12.5, Manassas VA (US East): 2 vCPU AMD EPYC Genoa (Zen 4: fast PEXT/BMI2), 4 GB RAM, 64 GB SSD, Ubuntu 24.04 |
| Address | 152.53.36.42 (IPv6 2a0a:4cc0:2000:15c:64d4:5eff:feae:753b, not in DNS yet) |
| Domain | 2048coach.com at Porkbun: `A` records for the apex and `www`; no proxy |
| Cost | €9.18/month (netcup, monthly term) + $11.08/year (domain) |
| Firewall | netcup's firewall: inbound TCP 22/80/443 and ICMP only. SSH by key only (root) |

## How it runs

- **Caddy** (`deploy/Caddyfile`): HTTPS with automatic Let's Encrypt certificates, HSTS, `www` → apex.
  - It proxies to the app on 127.0.0.1:8048 and sets `X-Forwarded-For` to the real client address. A client's own
    `X-Forwarded-For` is ignored (checked).
- **The app** (`deploy/2048coach.service`, user `coach`, `/opt/2048-coach`): `node server/src/index.ts` with
  `TRUST_PROXY=1`.
  - It keeps one resident engine (`build/analyze`, ~0.8 GB) and runs reviews in short-lived engine processes.
  - systemd restarts it if it stops. It is sandboxed (read-only system, private /tmp) and capped at 3 GB of memory.
- **The engine** is built on the server (`-march=native`, for its CPU) from the repo at the deployed commit.
- **The networks** are not in git. `deploy/push-weights.sh` copies the five files the engine opens (~0.9 GB, checked
  with strace) to `/opt/2048-coach/weights`.
- **System:** UTC, automatic security updates, 2 GB swap.

## Common tasks

```bash
# deploy the current main branch (pull, rebuild engine + web app, restart): push to GitHub first
ssh root@152.53.36.42 'bash -s' < deploy/setup.sh
# new or changed networks
deploy/push-weights.sh root@152.53.36.42 && ssh root@152.53.36.42 systemctl restart 2048coach
# logs (one JSON line per API request: method, path, status, ms; no IPs, no bodies)
ssh root@152.53.36.42 journalctl -u 2048coach -f
ssh root@152.53.36.42 journalctl -u caddy -n 50
# health
curl -s https://2048coach.com/api/health
# QA against the live site
cd app && node qa/run-journeys.mjs --base https://2048coach.com && node qa/run-lighthouse.mjs --base https://2048coach.com
```

## Checked at launch (2026-10-11)

- All 19 browser journeys pass against https://2048coach.com.
- Lighthouse: 100 for accessibility, best practices and SEO; 98-100 for performance (one mobile run at 89 was noise).
- An analysis takes 1-5 ms on the server. The network adds the rest (~0.2 s for a user ~190 ms away; far less within the US).
- After a reboot the site is back in ~15 s.

## Open

- **IPv6:** the server has an address, but no `AAAA` records yet. Inbound IPv6 through netcup's firewall is untested,
  and a broken `AAAA` could also break certificate renewal. IPv4 reaches everyone.
- **Snapshot:** take one in the netcup panel after changes (free, one exportable).
- **No uptime monitoring yet.**
