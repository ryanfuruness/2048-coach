#!/usr/bin/env bash
# Provision or update the 2048 Coach server (Ubuntu 24.04, run as root). Safe to run again: it updates the code,
# rebuilds the engine and the web app, and restarts the service.
#   ssh root@SERVER 'bash -s' < deploy/setup.sh
# The serving weights are not in git: deploy/push-weights.sh copies them to /opt/2048-coach/weights first.
set -euo pipefail
REPO=https://github.com/ryanfuruness/2048-coach.git
DIR=/opt/2048-coach
export DEBIAN_FRONTEND=noninteractive

# ---- system: UTC, updates, swap ----
timedatectl set-timezone UTC
apt-get update -q
apt-get upgrade -yq
apt-get install -yq build-essential git curl ca-certificates gnupg unattended-upgrades \
  debian-keyring debian-archive-keyring apt-transport-https
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'X'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
X
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# ---- Node 24 (NodeSource) and Caddy (official repository) ----
if ! node -v 2>/dev/null | grep -q '^v24'; then
  curl -fsSL https://deb.nodesource.com/setup_24.x | bash -
  apt-get install -yq nodejs
fi
if ! command -v caddy >/dev/null; then
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -q
  apt-get install -yq caddy
fi

# ---- the app user and the code ----
id coach >/dev/null 2>&1 || useradd --system --create-home --home-dir /var/lib/coach --shell /usr/sbin/nologin coach
# (the directory may already hold the weights, copied before the first run: init in place instead of cloning)
mkdir -p "$DIR"
git config --global --get-all safe.directory | grep -qx "$DIR" || git config --global --add safe.directory "$DIR"
[ -d "$DIR/.git" ] || git -C "$DIR" init -q -b main
git -C "$DIR" remote get-url origin >/dev/null 2>&1 || git -C "$DIR" remote add origin "$REPO"
git -C "$DIR" fetch -q --depth 1 origin main
git -C "$DIR" reset -q --hard origin/main
mkdir -p "$DIR/weights"
chown -R coach:coach "$DIR"

# ---- build: the engine (for this CPU: -march=native) and the web app ----
sudo -u coach make -C "$DIR" -j"$(nproc)" build/analyze
cd "$DIR/app"
sudo -u coach env PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm ci --no-audit --no-fund
sudo -u coach npm run build

# ---- service and proxy ----
install -m 644 "$DIR/deploy/2048coach.service" /etc/systemd/system/2048coach.service
install -m 644 "$DIR/deploy/Caddyfile" /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable -q 2048coach caddy
if [ -f "$DIR/weights/serve/v6c_i16.wp" ]; then
  systemctl restart 2048coach
else
  echo "weights missing: run deploy/push-weights.sh, then: systemctl restart 2048coach"
fi
systemctl restart caddy
echo "setup done: $(git -C "$DIR" log --oneline -1)"
