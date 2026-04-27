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
# 1. Python 의존성 (system-wide; pcb_bootstrap이 root로 실행되므로 root Python에 설치)
# ─────────────────────────────────────────────
PIP_PKGS=(
    pymodbus                       # Modbus RTU 클라이언트
    pyserial                       # serial transport (pymodbus 의존)
    redis                          # Redis 클라이언트
    pyyaml                         # config.yaml 파싱
    adafruit-circuitpython-dht     # DHT11 (env_sensors.py)
    mpu6050-raspberrypi            # MPU6050 (env_sensors.py)
)

echo "[1/4] Installing Python dependencies..."
# Bookworm 이후 Pi OS는 PEP 668 protected → 시스템 전역 설치는 --break-system-packages 필요.
# 구 OS에서는 해당 옵션이 없을 수 있으니 plain install 먼저 시도 후 fallback.
if ! python3 -m pip install --quiet "${PIP_PKGS[@]}" 2>/dev/null; then
    python3 -m pip install --break-system-packages --quiet "${PIP_PKGS[@]}"
fi

# ─────────────────────────────────────────────
# 2. systemd unit 파일 복사
# ─────────────────────────────────────────────
echo "[2/4] Copying systemd unit files..."
install -m 644 "$DAEMON_DIR/pcb_bootstrap.service"  "$SYSTEMD_DIR/pcb_bootstrap.service"
install -m 644 "$DAEMON_DIR/control_board.service" "$SYSTEMD_DIR/control_board.service"

# ─────────────────────────────────────────────
# 3. daemon-reload + enable
# ─────────────────────────────────────────────
echo "[3/4] Reloading systemd, enabling pcb_bootstrap.service..."
systemctl daemon-reload
systemctl enable pcb_bootstrap.service

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
echo "Useful commands:"
echo "  sudo journalctl -u pcb_bootstrap.service -n 20    # detection log"
echo "  sudo journalctl -u control_board.service -n 20    # control_board (stub)"
echo "  sudo systemctl restart pcb_bootstrap.service      # re-detect"
