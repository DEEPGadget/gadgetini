#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_DIR="/etc/systemd/system"

SERVICES=(
    "data_crawler.service"
    "gadgetini_net_up.service"
    "nvidia-pm.service"
)

echo "=== Configuring USB Gadget Network ==="
sudo bash "${SCRIPT_DIR}/../../../configure/usb_net/usb-gadget-host.sh"
echo ""

echo "=== Installing Python venv and dependencies ==="
sudo mkdir -p /opt/gadgetini
sudo apt install -y python3.12-venv
sudo python3 -m venv /opt/gadgetini/venv
sudo /opt/gadgetini/venv/bin/python -m pip install --upgrade pip
sudo /opt/gadgetini/venv/bin/python -m pip install redis jsons rich
echo "  venv ready at /opt/gadgetini/venv"

echo ""
echo "=== Copying service files ==="
for svc in "${SERVICES[@]}"; do
    sudo cp -f "${SCRIPT_DIR}/${svc}" "${SYSTEMD_DIR}/"
    echo "  Copied: ${svc}"
done

# mlnx template: copy only (no [Install] section, managed by OFED)
sudo cp -f "${SCRIPT_DIR}/mlnx_interface_mgr@.service" "${SYSTEMD_DIR}/"
echo "  Copied: mlnx_interface_mgr@.service (template only)"

echo ""
echo "=== Reloading systemd ==="
sudo systemctl daemon-reload

echo ""
echo "=== Enabling and starting services ==="
for svc in "${SERVICES[@]}"; do
    sudo systemctl enable "${svc}"
    sudo systemctl restart "${svc}"
    echo "  Enabled & started: ${svc}"
done

echo ""
echo "=== Service status ==="
for svc in "${SERVICES[@]}"; do
    echo "--- ${svc} ---"
    sudo systemctl status "${svc}" --no-pager -l
    echo ""
done
