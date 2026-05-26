#!/usr/bin/env bash
# control_board installer
#   - Install Python dependencies
#   - Register systemd units (pcb_bootstrap.service, control_board.service)
#   - Enable pcb_bootstrap.service and run a verification pass
#
# Usage: sudo bash install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DAEMON_DIR="$REPO_ROOT/src/configure/daemons/gadgetini"
SYSTEMD_DIR="/etc/systemd/system"

if [[ $EUID -ne 0 ]]; then
    echo "Run as root: sudo bash $0" >&2
    exit 1
fi

echo "=== control_board installer ==="
echo "Repo: $REPO_ROOT"
echo

# ─────────────────────────────────────────────
# 1. Python dependencies - requirements.txt is the source of truth.
#   pcb_bootstrap runs as root, control_board as gadgetini -> install into both site-packages.
# ─────────────────────────────────────────────
REQ_FILE="$SCRIPT_DIR/requirements.txt"

echo "[1/4] Installing Python dependencies from $REQ_FILE ..."
# Pi OS since Bookworm is PEP 668 protected -> system-wide install needs --break-system-packages.
# Older OS versions may not have this flag, so try plain install first and fall back.
pip_install() {
    local py_user="$1"; shift
    if [[ -n "$py_user" ]]; then
        sudo -u "$py_user" python3 -m pip install --quiet -r "$REQ_FILE" 2>/dev/null \
            || sudo -u "$py_user" python3 -m pip install --break-system-packages --quiet -r "$REQ_FILE"
    else
        python3 -m pip install --quiet -r "$REQ_FILE" 2>/dev/null \
            || python3 -m pip install --break-system-packages --quiet -r "$REQ_FILE"
    fi
}
pip_install ""           # root (pcb_bootstrap.service)
pip_install "gadgetini"  # gadgetini user (control_board.service)

# ─────────────────────────────────────────────
# 2. Copy systemd unit files
# ─────────────────────────────────────────────
echo "[2/4] Copying systemd unit files..."
install -m 644 "$DAEMON_DIR/pcb_bootstrap.service"  "$SYSTEMD_DIR/pcb_bootstrap.service"
install -m 644 "$DAEMON_DIR/control_board.service" "$SYSTEMD_DIR/control_board.service"
install -m 644 "$DAEMON_DIR/pcb_watcher.service"   "$SYSTEMD_DIR/pcb_watcher.service"

# ─────────────────────────────────────────────
# 3. daemon-reload + enable
# ─────────────────────────────────────────────
echo "[3/4] Reloading systemd, enabling pcb_bootstrap.service + pcb_watcher.service..."
systemctl daemon-reload
systemctl enable pcb_bootstrap.service
systemctl enable --now pcb_watcher.service

# ─────────────────────────────────────────────
# 4. One-shot verification run
# ─────────────────────────────────────────────
echo "[4/4] Triggering pcb_bootstrap.service for verification..."
systemctl restart pcb_bootstrap.service
sleep 2

echo
echo "=== install complete ==="
echo
echo "pcb_bootstrap.service status:"
systemctl --no-pager status pcb_bootstrap.service | head -8 || true
echo
echo "pcb_watcher.service status:"
systemctl --no-pager status pcb_watcher.service | head -8 || true
echo
echo "Useful commands:"
echo "  sudo journalctl -u pcb_bootstrap.service -n 20    # boot-time detection log"
echo "  sudo journalctl -u pcb_watcher.service -f         # runtime hot-plug watcher"
echo "  sudo journalctl -u control_board.service -n 20    # control_board (stub)"
echo "  sudo systemctl restart pcb_bootstrap.service      # re-detect"
