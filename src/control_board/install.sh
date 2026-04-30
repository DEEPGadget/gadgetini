#!/usr/bin/env bash
# control_board installer
#   - Python 의존성 설치
#   - systemd unit 등록 (pcb_bootstrap.service, control_board.service)
#   - pcb_bootstrap.service enable + 검증 실행
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
# 1. Python 의존성 — requirements.txt가 source of truth.
#   pcb_bootstrap은 root, control_board는 gadgetini로 실행 → 양쪽 site-packages에 모두 설치.
# ─────────────────────────────────────────────
REQ_FILE="$SCRIPT_DIR/requirements.txt"

echo "[1/4] Installing Python dependencies from $REQ_FILE ..."
# Bookworm 이후 Pi OS는 PEP 668 protected → 시스템 전역 설치는 --break-system-packages 필요.
# 구 OS에서는 해당 옵션이 없을 수 있으니 plain install 먼저 시도 후 fallback.
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
# 2. systemd unit 파일 복사
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
# 4. 검증 실행 (1회)
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
